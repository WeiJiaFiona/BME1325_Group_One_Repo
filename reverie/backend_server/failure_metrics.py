from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Iterable, Mapping, Optional


DEFAULT_FAILURE_THRESHOLD = 0.1
DEFAULT_SYSTEM_FAILED_COMPARATOR = "gt"

DEFAULT_CTAS_TARGET_WAIT_MINUTES = {
    "1": 0,
    "2": 15,
    "3": 30,
    "4": 60,
    "5": 120,
}

DEFAULT_ED_LOS_FAILURE_THRESHOLD_MINUTES = 720
DEFAULT_SEVERE_TRAUMA_SURGERY_TARGET_MINUTES = 90

DEFAULT_DOCTOR_QUEUE_OVERFLOW_THRESHOLD = 20
DEFAULT_LAB_QUEUE_OVERFLOW_THRESHOLD = 15
DEFAULT_IMAGING_QUEUE_OVERFLOW_THRESHOLD = 10
DEFAULT_OVERFLOW_EXPOSURE_MINUTES = 30

_REASON_ORDER = [
    "walkout_lwbs",
    "boarding_timeout",
    "ctas_target_wait_violation",
    "ed_los_over_threshold",
    "queue_overflow_exposure",
    "severe_trauma_time_to_surgery_violation",
    "critical_outcome_event",
]


def normalize_failure_meta(meta: dict | None) -> dict:
    payload = dict(meta or {})
    comparator = str(payload.get("system_failed_comparator", DEFAULT_SYSTEM_FAILED_COMPARATOR)).strip().lower()
    if comparator not in {"gt", "gte"}:
        comparator = DEFAULT_SYSTEM_FAILED_COMPARATOR

    ctas_targets = payload.get("ctas_target_wait_minutes") or {}
    normalized_ctas_targets = dict(DEFAULT_CTAS_TARGET_WAIT_MINUTES)
    if isinstance(ctas_targets, Mapping):
        for key, value in ctas_targets.items():
            key_text = str(key)
            try:
                normalized_ctas_targets[key_text] = float(value)
            except (TypeError, ValueError):
                continue

    def _coerce_float(key: str, default: float) -> float:
        try:
            return float(payload.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    return {
        "enable_failure_rate_metrics": bool(payload.get("enable_failure_rate_metrics", True)),
        "failure_threshold": _coerce_float("failure_threshold", DEFAULT_FAILURE_THRESHOLD),
        "system_failed_comparator": comparator,
        "ctas_target_wait_minutes": normalized_ctas_targets,
        "ed_los_failure_threshold_minutes": _coerce_float(
            "ed_los_failure_threshold_minutes",
            DEFAULT_ED_LOS_FAILURE_THRESHOLD_MINUTES,
        ),
        "severe_trauma_surgery_target_minutes": _coerce_float(
            "severe_trauma_surgery_target_minutes",
            DEFAULT_SEVERE_TRAUMA_SURGERY_TARGET_MINUTES,
        ),
        "doctor_queue_overflow_threshold": _coerce_float(
            "doctor_queue_overflow_threshold",
            DEFAULT_DOCTOR_QUEUE_OVERFLOW_THRESHOLD,
        ),
        "lab_queue_overflow_threshold": _coerce_float(
            "lab_queue_overflow_threshold",
            DEFAULT_LAB_QUEUE_OVERFLOW_THRESHOLD,
        ),
        "imaging_queue_overflow_threshold": _coerce_float(
            "imaging_queue_overflow_threshold",
            DEFAULT_IMAGING_QUEUE_OVERFLOW_THRESHOLD,
        ),
        "overflow_exposure_minutes": _coerce_float(
            "overflow_exposure_minutes",
            DEFAULT_OVERFLOW_EXPOSURE_MINUTES,
        ),
        "enable_critical_outcome_failure": bool(payload.get("enable_critical_outcome_failure", False)),
    }


def collect_failure_metrics(
    personas,
    maze=None,
    data_collection=None,
    meta=None,
    curr_time=None,
    curr_step=0,
):
    normalized_meta = normalize_failure_meta(meta)
    patient_records = _extract_patient_records(data_collection)
    persona_map = _extract_persona_map(personas)
    patient_ids = sorted(set(persona_map.keys()) | set(patient_records.keys()))

    total_arrived_patients = len(patient_records) if patient_records else len(patient_ids)
    failed_patients = set()
    failure_reasons_by_patient: Dict[str, list[str]] = {}
    failed_at_step: Dict[str, int] = {}
    ctas_violations_by_level: Dict[str, int] = {}
    eligible_ctas_patients = 0
    severe_trauma_total = 0
    severe_trauma_success = 0

    def add_failure(patient_id: str, reason: str, step: int):
        if patient_id not in failure_reasons_by_patient:
            failure_reasons_by_patient[patient_id] = []
        if reason not in failure_reasons_by_patient[patient_id]:
            failure_reasons_by_patient[patient_id].append(reason)
        if patient_id not in failed_patients:
            failed_patients.add(patient_id)
            failed_at_step[patient_id] = step

    for patient_id in patient_ids:
        persona = persona_map.get(patient_id)
        record = patient_records.get(patient_id, {})
        scratch = _get_scratch_payload(persona)

        if not normalized_meta["enable_failure_rate_metrics"]:
            continue

        if _walkout_triggered(scratch, record):
            add_failure(patient_id, "walkout_lwbs", curr_step)

        if _boarding_timeout_triggered(scratch, record):
            add_failure(patient_id, "boarding_timeout", curr_step)

        ctas = _read_ctas(scratch, record)
        triage_completed_at = _read_timestamp(scratch, record, "triage_completed_at")
        first_doctor_contact_at = _read_timestamp(scratch, record, "first_doctor_contact_at")
        if ctas is not None and triage_completed_at is not None and first_doctor_contact_at is not None:
            eligible_ctas_patients += 1
            threshold_minutes = normalized_meta["ctas_target_wait_minutes"].get(
                str(ctas),
                DEFAULT_CTAS_TARGET_WAIT_MINUTES.get(str(ctas), None),
            )
            if threshold_minutes is not None:
                wait_minutes = _minutes_between(first_doctor_contact_at, triage_completed_at)
                if wait_minutes is not None:
                    grace_minutes = 1.0 if str(ctas) == "1" else 0.0
                    if wait_minutes > (float(threshold_minutes) + grace_minutes):
                        add_failure(patient_id, "ctas_target_wait_violation", curr_step)
                        ctas_violations_by_level[str(ctas)] = ctas_violations_by_level.get(str(ctas), 0) + 1

        ed_arrival_at = _read_timestamp(scratch, record, "ed_arrival_at")
        ed_exit_at = _read_timestamp(scratch, record, "ed_exit_at")
        if ed_arrival_at is not None and ed_exit_at is not None:
            los_minutes = _minutes_between(ed_exit_at, ed_arrival_at)
            if los_minutes is not None and los_minutes > normalized_meta["ed_los_failure_threshold_minutes"]:
                add_failure(patient_id, "ed_los_over_threshold", curr_step)

        queue_exposure = _get_value(scratch, "queue_exposure") or _get_value(record, "queue_exposure") or {}
        if _queue_overflow_triggered(queue_exposure, normalized_meta):
            add_failure(patient_id, "queue_overflow_exposure", curr_step)

        is_severe_trauma = bool(_get_value(scratch, "is_severe_trauma", _get_value(record, "is_severe_trauma", False)))
        if is_severe_trauma:
            severe_trauma_total += 1
            surgery_or_transfer_at = _read_timestamp(scratch, record, "surgery_or_transfer_at")
            if ed_arrival_at is not None:
                threshold = normalized_meta["severe_trauma_surgery_target_minutes"]
                if surgery_or_transfer_at is not None:
                    trauma_minutes = _minutes_between(surgery_or_transfer_at, ed_arrival_at)
                    if trauma_minutes is not None:
                        if trauma_minutes > threshold:
                            add_failure(patient_id, "severe_trauma_time_to_surgery_violation", curr_step)
                        else:
                            severe_trauma_success += 1
                else:
                    now_dt = _parse_time(curr_time)
                    if now_dt is not None:
                        trauma_minutes = _minutes_between(now_dt, ed_arrival_at)
                        if trauma_minutes is not None and trauma_minutes > threshold:
                            add_failure(patient_id, "severe_trauma_time_to_surgery_violation", curr_step)

        if normalized_meta["enable_critical_outcome_failure"] and _critical_outcome_triggered(record):
            add_failure(patient_id, "critical_outcome_event", curr_step)

    failure_reason_counts = {reason: 0 for reason in _REASON_ORDER}
    for reasons in failure_reasons_by_patient.values():
        for reason in reasons:
            if reason in failure_reason_counts:
                failure_reason_counts[reason] += 1

    if total_arrived_patients <= 0:
        failure_rate = 0.0
        system_failed = False
    else:
        failure_rate = len(failed_patients) / float(total_arrived_patients)
        comparator = normalized_meta["system_failed_comparator"]
        if comparator == "gte":
            system_failed = failure_rate >= normalized_meta["failure_threshold"]
        else:
            system_failed = failure_rate > normalized_meta["failure_threshold"]

    if eligible_ctas_patients == 0:
        ctas_compliance_rate = None
    else:
        ctas_target_wait_violation_count = failure_reason_counts["ctas_target_wait_violation"]
        ctas_compliance_rate = 1.0 - (ctas_target_wait_violation_count / float(eligible_ctas_patients))

    if severe_trauma_total == 0:
        severe_trauma_success_rate = None
    else:
        severe_trauma_success_rate = severe_trauma_success / float(severe_trauma_total)

    return {
        "total_arrived_patients": int(total_arrived_patients),
        "failed_patients": sorted(failed_patients),
        "failed_patients_count": int(len(failed_patients)),
        "failure_rate": float(failure_rate),
        "system_failed": bool(system_failed),
        "failure_threshold": float(normalized_meta["failure_threshold"]),
        "system_failed_comparator": normalized_meta["system_failed_comparator"],
        "failure_reason_counts": failure_reason_counts,
        "failure_reasons_by_patient": failure_reasons_by_patient,
        "failed_at_step": failed_at_step,
        "lwbs_count": int(failure_reason_counts["walkout_lwbs"]),
        "boarding_timeout_count": int(failure_reason_counts["boarding_timeout"]),
        "ctas_target_wait_violation_count": int(failure_reason_counts["ctas_target_wait_violation"]),
        "ed_los_over_threshold_count": int(failure_reason_counts["ed_los_over_threshold"]),
        "queue_overflow_exposure_count": int(failure_reason_counts["queue_overflow_exposure"]),
        "severe_trauma_time_to_surgery_violation_count": int(
            failure_reason_counts["severe_trauma_time_to_surgery_violation"]
        ),
        "critical_outcome_event_count": int(failure_reason_counts["critical_outcome_event"]),
        "ctas_compliance_rate": ctas_compliance_rate,
        "ctas_violations_by_level": ctas_violations_by_level,
        "severe_trauma_success_rate": severe_trauma_success_rate,
    }


def _extract_persona_map(personas: Any) -> Dict[str, Any]:
    if isinstance(personas, Mapping):
        items = personas.items()
    elif personas is None:
        items = []
    else:
        items = []
        for persona in personas:
            name = _get_value(persona, "name")
            if name:
                items.append((str(name), persona))

    result: Dict[str, Any] = {}
    for patient_id, persona in items:
        if _is_patient_like(patient_id, persona):
            result[str(patient_id)] = persona
    return result


def _extract_patient_records(data_collection: Any) -> Dict[str, dict]:
    if not isinstance(data_collection, Mapping):
        return {}
    if isinstance(data_collection.get("Patient"), Mapping):
        return {str(k): v for k, v in data_collection.get("Patient", {}).items()}
    return {
        str(k): v
        for k, v in data_collection.items()
        if isinstance(v, Mapping) and (str(k).lower().startswith("patient") or "boarding_timeout_event" in v)
    }


def _is_patient_like(patient_id: str, persona: Any) -> bool:
    role = _get_value(persona, "role")
    if role == "Patient":
        return True
    scratch = _get_scratch_payload(persona)
    if scratch:
        for key in ("CTAS", "ctas", "state", "ICD", "injuries_zone", "walkout_recorded", "boarding_timeout_recorded"):
            if _has_key(scratch, key):
                return True
    return str(patient_id).lower().startswith("patient")


def _get_scratch_payload(persona: Any) -> Any:
    return _get_value(persona, "scratch", {})


def _has_key(payload: Any, key: str) -> bool:
    if isinstance(payload, Mapping):
        return key in payload
    return hasattr(payload, key)


def _get_value(payload: Any, key: str, default: Any = None) -> Any:
    if payload is None:
        return default
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _read_ctas(scratch: Any, record: Any) -> Optional[str]:
    for container in (scratch, record):
        for key in ("ctas", "CTAS"):
            value = _get_value(container, key)
            if value in (None, "", 0, "0"):
                continue
            return str(value)
    return None


def _walkout_triggered(scratch: Any, record: Any) -> bool:
    if bool(_get_value(scratch, "walkout_recorded", False)):
        return True
    return any(
        _event_occurred(record, key)
        for key in ("walkout_event", "lwbs_event", "left_department_by_choice")
    )


def _boarding_timeout_triggered(scratch: Any, record: Any) -> bool:
    if _event_occurred(record, "boarding_timeout_event"):
        return True
    return bool(_get_value(scratch, "boarding_timeout_recorded", False))


def _critical_outcome_triggered(record: Any) -> bool:
    return any(
        _event_occurred(record, key)
        for key in (
            "critical_outcome_event",
            "mortality_event",
            "unexpected_icu_deterioration_event",
        )
    )


def _event_occurred(record: Any, key: str) -> bool:
    event = _get_value(record, key)
    return isinstance(event, Mapping) and bool(event.get("occurred", False))


def _read_timestamp(scratch: Any, record: Any, key: str) -> Optional[_dt.datetime]:
    for container in (scratch, record):
        value = _get_value(container, key)
        parsed = _parse_time(value)
        if parsed is not None:
            return parsed
    return None


def _parse_time(value: Any) -> Optional[_dt.datetime]:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return _dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _minutes_between(later: _dt.datetime, earlier: _dt.datetime) -> Optional[float]:
    try:
        return (later - earlier).total_seconds() / 60.0
    except Exception:
        return None


def _queue_overflow_triggered(queue_exposure: Any, normalized_meta: dict) -> bool:
    if not isinstance(queue_exposure, Mapping):
        return False
    thresholds = {
        "doctor": normalized_meta["doctor_queue_overflow_threshold"],
        "lab": normalized_meta["lab_queue_overflow_threshold"],
        "imaging": normalized_meta["imaging_queue_overflow_threshold"],
    }
    exposure_threshold = normalized_meta["overflow_exposure_minutes"]
    for queue_name, queue_threshold in thresholds.items():
        payload = queue_exposure.get(queue_name)
        if not isinstance(payload, Mapping):
            continue
        try:
            max_queue_len = float(payload.get("max_queue_len", 0))
            exposure_minutes = float(payload.get("exposure_minutes", 0))
        except (TypeError, ValueError):
            continue
        if max_queue_len > queue_threshold and exposure_minutes > exposure_threshold:
            return True
    return False
