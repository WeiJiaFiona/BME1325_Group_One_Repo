from __future__ import annotations

import bisect
import os
from typing import Any
from ed_priority import patient_ctas_level, queue_entry_priority_key


def patient_name_in_queue(queue: list[Any], patient_name: str) -> bool:
    return any(isinstance(entry, (list, tuple)) and len(entry) >= 2 and str(entry[1]) == str(patient_name) for entry in queue)


def patient_has_bedside_reinsert_evidence(patient: Any) -> bool:
    scratch = getattr(patient, "scratch", None)
    if scratch is None:
        return False
    return (
        getattr(scratch, "ed_arrival_minute", None) is not None
        and getattr(scratch, "triage_completed_minute", None) is not None
    )


def patient_is_active_bedside_queue_candidate(patient: Any) -> bool:
    scratch = getattr(patient, "scratch", None)
    if scratch is None:
        return False
    if getattr(scratch, "left_without_being_seen", False):
        return False
    if getattr(scratch, "exempt_from_data_collection", False):
        return False
    state = getattr(scratch, "state", None)
    if state not in {"WAITING_FOR_NURSE", "WAITING_FOR_TEST"}:
        return False
    return patient_has_bedside_reinsert_evidence(patient)


def cleanup_bedside_nurse_waiting_queue(
    *,
    queue: list[Any],
    personas: dict[str, Any],
) -> dict[str, int]:
    removed = {
        "malformed": 0,
        "missing_patient": 0,
        "stale_or_invalid_patient": 0,
        "duplicate": 0,
    }
    seen: set[str] = set()
    cleaned: list[Any] = []
    for entry in list(queue):
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            removed["malformed"] += 1
            continue
        patient_name = str(entry[1])
        patient = personas.get(patient_name)
        if patient is None:
            removed["missing_patient"] += 1
            continue
        if not patient_is_active_bedside_queue_candidate(patient):
            removed["stale_or_invalid_patient"] += 1
            continue
        if patient_name in seen:
            removed["duplicate"] += 1
            continue
        seen.add(patient_name)
        cleaned.append(entry)
    if len(cleaned) != len(queue):
        queue[:] = cleaned
        try:
            queue.sort(key=lambda item: item[0])
        except Exception:
            pass
    return removed


def _patient_record(data_collection: dict[str, Any] | None, patient_name: str) -> dict[str, Any] | None:
    if not isinstance(data_collection, dict):
        return None
    patient_bucket = data_collection.setdefault("Patient", {})
    if not isinstance(patient_bucket, dict):
        return None
    record = patient_bucket.setdefault(patient_name, {})
    return record if isinstance(record, dict) else None


def guarded_bedside_reinsert(
    *,
    queue: list[Any],
    patient: Any,
    priority: int | float,
    data_collection: dict[str, Any] | None = None,
    max_reinsert_count: int = 3,
    increment_reinsert_count: bool = True,
) -> tuple[bool, str]:
    patient_name = str(getattr(patient, "name", ""))
    if not patient_name:
        return False, "missing_patient_name"
    if patient_name_in_queue(queue, patient_name):
        return False, "already_in_bedside_nurse_waiting"
    if not patient_has_bedside_reinsert_evidence(patient):
        return False, "missing_arrival_or_triage_evidence"

    scratch = getattr(patient, "scratch", None)
    current_count = int(getattr(scratch, "bedside_reinsert_count", 0) or 0)
    next_count = current_count + 1 if increment_reinsert_count else current_count
    setattr(scratch, "bedside_reinsert_count", next_count)
    record = _patient_record(data_collection, patient_name)
    if record is not None:
        record["bedside_reinsert_count"] = next_count
    if increment_reinsert_count and next_count > int(max_reinsert_count):
        if not getattr(scratch, "bedside_reinsert_warning_emitted", False):
            setattr(scratch, "bedside_reinsert_warning_emitted", True)
            return False, "reinsert_count_exceeded_warning"
        return False, "reinsert_count_exceeded"

    bisect.insort_right(queue, [priority, patient_name])
    return True, "inserted"


def _scan_telemetry_enabled() -> bool:
    return str(os.environ.get("EDSIM_BEDSIDE_QUEUE_SCAN_TELEMETRY", "")).strip().lower() in {"1", "true", "yes", "y"}


def _record_scan_event(
    *,
    data_collection: dict[str, Any] | None,
    runtime_step: int | None,
    nurse_name: str | None,
    patient_name: str | None,
    entry: Any,
    scan_result: str,
    skip_reason: str | None,
    patient: Any = None,
    zone: Any = None,
) -> None:
    if not _scan_telemetry_enabled() or not isinstance(data_collection, dict):
        return
    scratch = getattr(patient, "scratch", None)
    queue_priority = None
    if isinstance(entry, (list, tuple)) and len(entry) >= 1:
        queue_priority = entry[0]
    data_collection.setdefault("Bedside_Queue_Scan_Events", []).append(
        {
            "step": int(runtime_step or 0),
            "nurse": nurse_name,
            "patient": patient_name,
            "queue": "bedside_nurse_waiting",
            "scan_result": scan_result,
            "skip_reason": skip_reason,
            "state": getattr(scratch, "state", None) if scratch is not None else None,
            "zone": zone,
            "queue_priority": queue_priority,
        }
    )


def select_bedside_patient_for_assignment(
    *,
    queue: list[Any],
    personas: dict[str, Any],
    zone_has_space,
    reserve_bed,
    assigned_patient_ids_this_step: set[str],
    bed_tracked_zones: set[str] | None = None,
    data_collection: dict[str, Any] | None = None,
    runtime_step: int | None = None,
    nurse_name: str | None = None,
    max_scan_skip_events: int = 5,
) -> tuple[Any | None, Any | None, Any | None]:
    bed_tracked_zones = bed_tracked_zones or set()
    selected_patient = None
    selected_entry = None
    reserved_bed = None
    skip_events_recorded = 0
    try:
        queue.sort(key=lambda entry: queue_entry_priority_key(entry, personas))
    except Exception:
        pass
    for entry in list(queue):
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            if skip_events_recorded < max_scan_skip_events:
                _record_scan_event(
                    data_collection=data_collection,
                    runtime_step=runtime_step,
                    nurse_name=nurse_name,
                    patient_name=None,
                    entry=entry,
                    scan_result="skipped",
                    skip_reason="malformed_entry",
                )
                skip_events_recorded += 1
            try:
                queue.remove(entry)
            except ValueError:
                pass
            continue
        patient_name = str(entry[1])
        curr_persona = personas.get(patient_name)
        if not curr_persona:
            if skip_events_recorded < max_scan_skip_events:
                _record_scan_event(
                    data_collection=data_collection,
                    runtime_step=runtime_step,
                    nurse_name=nurse_name,
                    patient_name=patient_name,
                    entry=entry,
                    scan_result="skipped",
                    skip_reason="patient_missing",
                )
                skip_events_recorded += 1
            queue.remove(entry)
            continue
        zone = getattr(curr_persona.scratch, "next_room", None)
        if not zone:
            if skip_events_recorded < max_scan_skip_events:
                _record_scan_event(
                    data_collection=data_collection,
                    runtime_step=runtime_step,
                    nurse_name=nurse_name,
                    patient_name=patient_name,
                    entry=entry,
                    scan_result="skipped",
                    skip_reason="missing_next_room",
                    patient=curr_persona,
                    zone=zone,
                )
                skip_events_recorded += 1
            queue.remove(entry)
            continue
        if curr_persona.scratch.state not in {"WAITING_FOR_NURSE", "WAITING_FOR_TEST"}:
            if skip_events_recorded < max_scan_skip_events:
                _record_scan_event(
                    data_collection=data_collection,
                    runtime_step=runtime_step,
                    nurse_name=nurse_name,
                    patient_name=patient_name,
                    entry=entry,
                    scan_result="skipped",
                    skip_reason="state_not_ready",
                    patient=curr_persona,
                    zone=zone,
                )
                skip_events_recorded += 1
            queue.remove(entry)
            continue
        if patient_name in assigned_patient_ids_this_step:
            if skip_events_recorded < max_scan_skip_events:
                _record_scan_event(
                    data_collection=data_collection,
                    runtime_step=runtime_step,
                    nurse_name=nurse_name,
                    patient_name=patient_name,
                    entry=entry,
                    scan_result="skipped",
                    skip_reason="already_assigned_this_step",
                    patient=curr_persona,
                    zone=zone,
                )
                skip_events_recorded += 1
            continue
        if selected_patient is None and zone_has_space(zone):
            reserved_bed = reserve_bed(curr_persona, zone)
            if zone in bed_tracked_zones and not reserved_bed:
                if skip_events_recorded < max_scan_skip_events:
                    _record_scan_event(
                        data_collection=data_collection,
                        runtime_step=runtime_step,
                        nurse_name=nurse_name,
                        patient_name=patient_name,
                        entry=entry,
                        scan_result="skipped",
                        skip_reason="reserve_bed_failed",
                        patient=curr_persona,
                        zone=zone,
                    )
                    skip_events_recorded += 1
                continue
            selected_patient = curr_persona
            selected_entry = entry
            queue.remove(entry)
            assigned_patient_ids_this_step.add(patient_name)
            if isinstance(data_collection, dict):
                data_collection.setdefault("Selection_Events", []).append(
                    {
                        "step": int(runtime_step or 0),
                        "selector_role": "BedsideNurse",
                        "selector": nurse_name,
                        "queue": "bedside_nurse_waiting",
                        "selected_patient": patient_name,
                        "selected_patient_ctas": patient_ctas_level(curr_persona),
                        "candidate_ctas_order": [
                            patient_ctas_level(personas[str(candidate[1])])
                            for candidate in queue[:5]
                            if isinstance(candidate, (list, tuple))
                            and len(candidate) >= 2
                            and str(candidate[1]) in personas
                        ],
                        "priority_inversion_flag": False,
                        "priority_skip_reason": None,
                    }
                )
            _record_scan_event(
                data_collection=data_collection,
                runtime_step=runtime_step,
                nurse_name=nurse_name,
                patient_name=patient_name,
                entry=entry,
                scan_result="selected",
                skip_reason=None,
                patient=curr_persona,
                zone=zone,
            )
            continue
        if selected_patient is None:
            if skip_events_recorded < max_scan_skip_events:
                _record_scan_event(
                    data_collection=data_collection,
                    runtime_step=runtime_step,
                    nurse_name=nurse_name,
                    patient_name=patient_name,
                    entry=entry,
                    scan_result="skipped",
                    skip_reason="zone_full",
                    patient=curr_persona,
                    zone=zone,
                )
                skip_events_recorded += 1
        if entry[0] > 3:
            entry[0] -= 1
    return selected_patient, selected_entry, reserved_bed
