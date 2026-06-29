#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")

TRACE_COLUMNS = [
    "run_id",
    "patient_id",
    "ctas_level",
    "event_minute",
    "event_type",
    "actor_id",
    "actor_role",
    "from_state",
    "to_state",
    "zone",
    "bed_id",
    "tile",
    "queue_name",
    "failure_reason",
    "raw_event_source",
]

FAILURE_COLUMNS = [
    "patient_id",
    "ctas_level",
    "arrival_minute",
    "triage_start_minute",
    "triage_complete_minute",
    "bedside_queue_enter_minute",
    "queue_pop_minute",
    "bed_assigned_minute",
    "first_doctor_contact_minute",
    "care_completed_minute",
    "exit_minute",
    "arrival_to_triage_min",
    "triage_to_queue_pop_min",
    "queue_pop_to_doctor_min",
    "arrival_to_pia_min",
    "last_event_minute",
    "last_event_type",
    "dominant_failure_stage",
    "failure_event",
    "human_readable_failure_chain",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _patient_bucket(data_collection: Any) -> dict[str, dict[str, Any]]:
    payload = data_collection.get("Patient", {}) if isinstance(data_collection, dict) else {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)} if isinstance(payload, dict) else {}


def _first_events(data_collection: Any, role_key: str, event_key: str, actor_field: str) -> dict[str, dict[str, Any]]:
    bucket = data_collection.get(role_key, {}) if isinstance(data_collection, dict) else {}
    if not isinstance(bucket, dict):
        return {}
    flat: list[dict[str, Any]] = []
    for actor_name, actor_payload in bucket.items():
        if not isinstance(actor_payload, dict):
            continue
        for event in actor_payload.get(event_key) or []:
            if isinstance(event, dict):
                payload = dict(event)
                payload.setdefault(actor_field, actor_name)
                payload["patient"] = str(payload.get("patient") or "")
                flat.append(payload)
    flat.sort(key=lambda item: (item.get("step") is None, item.get("step"), item.get("patient")))
    result: dict[str, dict[str, Any]] = {}
    for item in flat:
        patient = item["patient"]
        if patient and patient not in result:
            result[patient] = item
    return result


def _triage_events(data_collection: Any) -> dict[str, dict[str, Any]]:
    bucket = data_collection.get("TriageNurse", {}) if isinstance(data_collection, dict) else {}
    if not isinstance(bucket, dict):
        return {}
    flat: list[dict[str, Any]] = []
    for nurse_name, nurse_payload in bucket.items():
        if not isinstance(nurse_payload, dict):
            continue
        for event in nurse_payload.get("Patients_Attended") or []:
            if isinstance(event, dict):
                flat.append(
                    {
                        "patient": str(event.get("patient") or ""),
                        "step": event.get("step"),
                        "nurse": str(event.get("nurse") or nurse_name),
                    }
                )
    flat.sort(key=lambda item: (item.get("step") is None, item.get("step"), item.get("patient")))
    result: dict[str, dict[str, Any]] = {}
    for item in flat:
        patient = item["patient"]
        if patient and patient not in result:
            result[patient] = item
    return result


def _event_row(**kwargs: Any) -> dict[str, Any]:
    return {column: kwargs.get(column, "") for column in TRACE_COLUMNS}


def build_patient_trace(run_dir: Path) -> dict[str, Any]:
    patient_rows = _read_csv(run_dir / "patient_level_results.csv")
    data_collection = _load_json(run_dir / "raw_data_collection.json")
    patient_records = _patient_bucket(data_collection)
    triage_events = _triage_events(data_collection)
    queue_events = _first_events(data_collection, "BedsideNurse", "Queue_Pop_Events", "nurse")
    doctor_events = _first_events(data_collection, "Doctor", "Doctor_Assignment_Events", "doctor")

    trace_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for row in patient_rows:
        run_id = str(row.get("run_id") or run_dir.name)
        patient_id = str(row.get("patient_id") or "")
        ctas = str(row.get("ctas_level") or "")
        record = patient_records.get(patient_id, {})
        zone = row.get("zone_assigned") or record.get("injuries_zone") or ""
        bed_id = record.get("bed_assignment") or ""
        arrival = _num(row.get("arrival_minute"))
        triage = _num(row.get("triage_complete_minute"))
        queue_pop = _num(row.get("queue_pop_minute"))
        doctor_contact = _num(row.get("first_doctor_contact_minute"))
        care_complete = _num(row.get("care_completed_minute"))
        exit_minute = _num(row.get("exit_minute"))

        if arrival is not None:
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=arrival, event_type="arrival", actor_id=patient_id, actor_role="Patient", to_state="WAITING_FOR_TRIAGE", zone="waiting room", bed_id=bed_id, raw_event_source="patient_record.ed_arrival_minute"))
        if triage is not None:
            triage_event = triage_events.get(patient_id, {})
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=triage, event_type="triage_complete", actor_id=triage_event.get("nurse", ""), actor_role="TriageNurse", from_state="TRIAGE", to_state="WAITING_FOR_NURSE", zone="waiting room", bed_id=bed_id, raw_event_source="patient_record.triage_completed_minute"))
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=triage, event_type="bedside_queue_enter", actor_id=patient_id, actor_role="Patient", from_state="WAITING_FOR_NURSE", to_state="WAITING_FOR_NURSE", zone="waiting room", bed_id=bed_id, queue_name="bedside_nurse_waiting", raw_event_source="inferred_from_triage_complete"))
        if queue_pop is not None:
            queue_event = queue_events.get(patient_id, {})
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=queue_pop, event_type="bedside_queue_pop", actor_id=queue_event.get("nurse", ""), actor_role="BedsideNurse", from_state="WAITING_FOR_NURSE", to_state="WAITING_FOR_FIRST_ASSESSMENT", zone=zone, bed_id=queue_event.get("reserved_bed") or bed_id, queue_name=queue_event.get("queue") or "bedside_nurse_waiting", raw_event_source="Queue_Pop_Events"))
        if doctor_contact is not None:
            doctor_event = doctor_events.get(patient_id, {})
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=doctor_contact, event_type="first_doctor_contact", actor_id=doctor_event.get("doctor", row.get("assigned_doctor") or ""), actor_role="Doctor", from_state="WAITING_FOR_FIRST_ASSESSMENT", to_state="WAITING_FOR_TEST_OR_RESULT", zone=zone, bed_id=bed_id, raw_event_source="patient_record.first_doctor_contact_minute"))
        if care_complete is not None:
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=care_complete, event_type="care_completed", actor_id=row.get("assigned_doctor") or "", actor_role="Doctor", from_state="WAITING_FOR_DOCTOR_OR_RESULT", to_state="WAITING_FOR_EXIT", zone=zone, bed_id=bed_id, raw_event_source="patient_record.care_completed_minute"))
        if exit_minute is not None:
            trace_rows.append(_event_row(run_id=run_id, patient_id=patient_id, ctas_level=ctas, event_minute=exit_minute, event_type="exit", actor_id=patient_id, actor_role="Patient", from_state=row.get("final_state") or "WAITING_FOR_EXIT", to_state="LEAVING", zone=zone, bed_id=bed_id, raw_event_source="patient_record.exit_minute"))

        if ctas in {"L1", "L2"} and str(row.get("pia_sdr_success")).lower() != "true":
            last_pairs = [(arrival, "arrival"), (triage, "triage_complete"), (queue_pop, "bedside_queue_pop"), (doctor_contact, "first_doctor_contact"), (care_complete, "care_completed"), (exit_minute, "exit")]
            available = [(minute, event_type) for minute, event_type in last_pairs if minute is not None]
            last_event_minute, last_event_type = available[-1] if available else ("", "")
            failure_rows.append(
                {
                    "patient_id": patient_id,
                    "ctas_level": ctas,
                    "arrival_minute": arrival if arrival is not None else "",
                    "triage_start_minute": arrival if arrival is not None else "",
                    "triage_complete_minute": triage if triage is not None else "",
                    "bedside_queue_enter_minute": triage if triage is not None else "",
                    "queue_pop_minute": queue_pop if queue_pop is not None else "",
                    "bed_assigned_minute": queue_pop if queue_pop is not None else "",
                    "first_doctor_contact_minute": doctor_contact if doctor_contact is not None else "",
                    "care_completed_minute": care_complete if care_complete is not None else "",
                    "exit_minute": exit_minute if exit_minute is not None else "",
                    "arrival_to_triage_min": row.get("arrival_to_triage_min", ""),
                    "triage_to_queue_pop_min": row.get("triage_to_queue_pop_min", ""),
                    "queue_pop_to_doctor_min": row.get("queue_pop_to_doctor_min", ""),
                    "arrival_to_pia_min": row.get("arrival_to_pia_min", ""),
                    "last_event_minute": last_event_minute,
                    "last_event_type": last_event_type,
                    "dominant_failure_stage": row.get("dominant_failure_stage", ""),
                    "failure_event": row.get("failure_event", ""),
                    "human_readable_failure_chain": f"arrival={arrival}, triage={triage}, queue_pop={queue_pop}, doctor={doctor_contact}, care={care_complete}, exit={exit_minute}, failure={row.get('failure_event', '')}, stage={row.get('dominant_failure_stage', '')}",
                }
            )

    trace_rows.sort(key=lambda item: (str(item["patient_id"]), float(item["event_minute"]) if item["event_minute"] not in ("", None) else 10**9, str(item["event_type"])))
    failure_rows.sort(key=lambda item: (item["ctas_level"], item["arrival_to_pia_min"] in ("", None), -(_num(item["arrival_to_pia_min"]) or -1), item["patient_id"]))
    top_failed = sorted(
        [row for row in patient_rows if row.get("failure_event") or str(row.get("pia_sdr_success")).lower() != "true"],
        key=lambda item: (item.get("arrival_to_pia_min") in ("", None), -(_num(item.get("arrival_to_pia_min")) or -1), str(item.get("patient_id"))),
    )[:20]

    with (run_dir / "patient_event_trace.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_COLUMNS)
        writer.writeheader()
        writer.writerows(trace_rows)
    with (run_dir / "critical_failure_trace.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FAILURE_COLUMNS)
        writer.writeheader()
        writer.writerows(failure_rows)
    with (run_dir / "top_failed_patient_trace.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(top_failed[0].keys()) if top_failed else ["patient_id"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(top_failed)

    return {
        "run_id": run_dir.name,
        "patient_event_trace_count": len(trace_rows),
        "critical_failure_trace_count": len(failure_rows),
        "top_failed_patient_count": len(top_failed),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export large tertiary patient traces.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", action="append", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.output_root)
    run_dirs = [root / run_id for run_id in args.run_id] if args.run_id else [path for path in root.iterdir() if path.is_dir() and path.name != "aggregate"]
    reports = [build_patient_trace(run_dir) for run_dir in run_dirs if run_dir.exists()]
    print(json.dumps({"runs": reports}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
