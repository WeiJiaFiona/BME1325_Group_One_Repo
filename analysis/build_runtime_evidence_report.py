from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = REPO_ROOT / "analysis" / "runtime_evidence_probe_report.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _patient_records(data_collection: Any) -> dict[str, dict[str, Any]]:
    if isinstance(data_collection, list):
        return {
            str(row.get("name") or row.get("patient_id") or row.get("id") or idx): row
            for idx, row in enumerate(data_collection, start=1)
            if isinstance(row, dict)
        }
    if not isinstance(data_collection, dict):
        return {}
    patients = data_collection.get("Patient", data_collection)
    if isinstance(patients, dict):
        return {str(k): v for k, v in patients.items() if isinstance(v, dict)}
    if isinstance(patients, list):
        return {
            str(row.get("name") or row.get("patient_id") or row.get("id") or idx): row
            for idx, row in enumerate(patients, start=1)
            if isinstance(row, dict)
        }
    return {}


def _count_non_null(records: dict[str, dict[str, Any]], *keys: str) -> int:
    return sum(1 for row in records.values() if any(row.get(key) not in (None, "") for key in keys))


def _count_event_true(records: dict[str, dict[str, Any]], key: str) -> int:
    total = 0
    for row in records.values():
        payload = row.get(key)
        if isinstance(payload, dict) and payload.get("occurred", False):
            total += 1
    return total


def _count_queue_exposure_records(records: dict[str, dict[str, Any]]) -> int:
    total = 0
    for row in records.values():
        payload = row.get("queue_exposure")
        if isinstance(payload, dict) and payload:
            total += 1
    return total


def _ctas_eligible_count(records: dict[str, dict[str, Any]]) -> int:
    total = 0
    for row in records.values():
        if row.get("triage_completed_minute") not in (None, "") and row.get("first_doctor_contact_minute") not in (None, ""):
            total += 1
    return total


def _max_queue_from_trace(queue_trace_path: Path, field: str) -> int:
    if not queue_trace_path.exists():
        return 0
    max_value = 0
    with queue_trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                max_value = max(max_value, int(payload.get(field, 0) or 0))
            except (TypeError, ValueError):
                continue
    return max_value


def build_runtime_evidence_report(
    *,
    sim_dir: str | Path,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    hospital_profile: str | None = None,
    load_factor: float | None = None,
    preload_patient_count: int | None = None,
    run_steps_requested: int | None = None,
) -> dict[str, Any]:
    sim_dir = Path(sim_dir)
    status_payload = _load_json(sim_dir / "sim_status.json")
    meta_payload = _load_json(sim_dir / "reverie" / "meta.json")
    data_collection_path = sim_dir / "reverie" / "data_collection.json"
    if not data_collection_path.exists():
        data_collection_path = sim_dir / "data_collection.json"
    data_collection = _load_json(data_collection_path)
    records = _patient_records(data_collection)
    queue_trace_path = sim_dir / "analysis" / "queue_trace_by_step.jsonl"

    minutes_per_step = int(meta_payload.get("time_scale_minutes_per_step", 1) or 1)
    run_steps_completed = int(status_payload.get("step", 0) or 0) + 1
    physical_window_minutes = run_steps_completed * minutes_per_step

    triage_completed_at_count = _count_non_null(records, "triage_completed_minute", "triage_completed_at")
    first_doctor_contact_at_count = _count_non_null(records, "first_doctor_contact_minute", "first_doctor_contact_at")
    ed_exit_at_count = _count_non_null(records, "ed_exit_minute", "ed_exit_at")
    queue_exposure_record_count = _count_queue_exposure_records(records)

    missing_fields: list[str] = []
    if triage_completed_at_count == 0:
        missing_fields.append("triage_completed_minute")
    if first_doctor_contact_at_count == 0:
        missing_fields.append("first_doctor_contact_minute")
    if queue_exposure_record_count == 0:
        missing_fields.append("queue_exposure")
    if ed_exit_at_count == 0:
        missing_fields.append("ed_exit_minute")

    report = {
        "hospital_profile": hospital_profile,
        "load_factor": load_factor,
        "preload_patient_count": preload_patient_count,
        "run_steps_requested": run_steps_requested,
        "run_steps_completed": run_steps_completed,
        "time_scale_minutes_per_step": minutes_per_step,
        "physical_window_minutes": physical_window_minutes,
        "total_arrived_patients": len(records),
        "ed_arrival_at_count": _count_non_null(records, "ed_arrival_minute", "ed_arrival_at"),
        "triage_completed_at_count": triage_completed_at_count,
        "first_doctor_contact_at_count": first_doctor_contact_at_count,
        "ed_exit_at_count": ed_exit_at_count,
        "queue_exposure_record_count": queue_exposure_record_count,
        "boarding_timeout_event_count": _count_event_true(records, "boarding_timeout_event"),
        "ctas_eligible_count": _ctas_eligible_count(records),
        "queue_trace_by_step_exists": queue_trace_path.exists(),
        "max_doctor_queue": _max_queue_from_trace(queue_trace_path, "doctor_queue_len"),
        "max_lab_queue": _max_queue_from_trace(queue_trace_path, "lab_queue_len"),
        "max_imaging_queue": _max_queue_from_trace(queue_trace_path, "imaging_queue_len"),
        "boarding_patient_count": _max_queue_from_trace(queue_trace_path, "boarding_patient_count"),
        "triage_completed_step_count": _count_non_null(records, "triage_completed_step"),
        "first_doctor_contact_step_count": _count_non_null(records, "first_doctor_contact_step"),
        "ed_exit_step_count": _count_non_null(records, "ed_exit_step"),
        "evidence_ready_for_failure_rate": triage_completed_at_count > 0 and queue_exposure_record_count > 0,
        "evidence_ready_for_success_rates": triage_completed_at_count > 0 and first_doctor_contact_at_count > 0 and queue_exposure_record_count > 0 and ed_exit_at_count > 0,
        "missing_evidence_fields": missing_fields,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
