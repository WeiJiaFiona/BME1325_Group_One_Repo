#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT, REPO_ROOT / "reverie" / "backend_server"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from analysis.large_tertiary_bedside_bed_audit import audit_run as audit_bedside_bed_run
from analysis.large_tertiary_ctas_priority_audit import audit_run as audit_ctas_priority_run
from analysis.large_tertiary_doctor_pia_audit import audit_run as audit_doctor_pia_run
from analysis.large_tertiary_flow_audit import build_flow_audit_for_run, write_flow_audit_aggregate
from analysis.large_tertiary_path_failure_audit import audit_run as audit_path_failure_run
from analysis.large_tertiary_patient_trace import build_patient_trace
from success_metrics import extract_patient_records


DEFAULT_SCENARIO_CSV = REPO_ROOT / "configs" / "cluster" / "auto_capacity_cn_benchmark_scenarios.csv"
DEFAULT_RAW_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "large_tertiary_ed_300_capacity_benchmark_raw"
DEFAULT_BENCHMARK_OUTPUT_ROOT = REPO_ROOT / "test_results" / "auto_capacity_large_tertiary_final"

CTAS_TARGET_MINUTES = {"L1": 0.0, "L2": 15.0, "L3": 30.0, "L4": 60.0, "L5": 120.0}
PATIENT_COLUMNS = [
    "run_id",
    "patient_id",
    "encounter_id",
    "ctas_level",
    "arrival_minute",
    "triage_complete_minute",
    "queue_pop_minute",
    "first_doctor_contact_minute",
    "care_completed_minute",
    "exit_minute",
    "arrival_to_triage_min",
    "triage_to_queue_pop_min",
    "queue_pop_to_doctor_min",
    "arrival_to_pia_min",
    "triage_to_pia_min",
    "doctor_to_care_complete_min",
    "arrival_to_exit_min",
    "pia_target_min",
    "pia_sdr_success",
    "failure_event",
    "dominant_failure_stage",
    "assigned_doctor",
    "doctor_dispatch_policy_at_contact",
    "zone_assigned",
    "testing_kind",
    "final_state",
    "final_destination",
    "queue_exposed",
    "bedside_nurse_exposure_minutes",
    "doctor_exposure_minutes",
]
TIMESERIES_COLUMNS = [
    "run_id",
    "sim_time_min",
    "active_patients",
    "completed_patients",
    "triage_queue_len",
    "bed_queue_len",
    "physician_queue_len",
    "diagnostic_queue_len",
    "occupied_rescue_beds",
    "occupied_high_acuity_beds",
    "occupied_observation_beds",
    "total_occupied_beds",
    "bed_occupancy_rate",
    "mean_physician_load",
    "max_physician_load",
    "nurse_busy_rate",
    "current_arrival_rate_per_hour",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_scenario_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def coerce_int(value: Any) -> int | None:
    number = coerce_float(value)
    return None if number is None else int(round(number))


def read_raw_paths(raw_output_root: Path, row: dict[str, Any]) -> dict[str, Path | None]:
    run_id = str(row["scenario_id"])
    output_dir = raw_output_root / str(row.get("experiment_group") or "") / run_id
    status_path = output_dir / "scenario_status.json"
    frozen = output_dir / "frozen_artifacts"
    return {
        "output_dir": output_dir,
        "status": status_path if status_path.exists() else None,
        "data_collection": frozen / "data_collection.json" if (frozen / "data_collection.json").exists() else None,
        "sim_status": frozen / "sim_status.json" if (frozen / "sim_status.json").exists() else None,
        "success_failure_report": output_dir / "success_failure_report.json"
        if (output_dir / "success_failure_report.json").exists()
        else None,
    }


def extract_artifacts(raw_output_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    paths = read_raw_paths(raw_output_root, row)
    status = load_json(paths["status"]) if paths["status"] else {}
    data_collection = load_json(paths["data_collection"]) if paths["data_collection"] else {}
    sim_status = load_json(paths["sim_status"]) if paths["sim_status"] else {}
    success_report = load_json(paths["success_failure_report"]) if paths["success_failure_report"] else {}
    sim_dir = status.get("sim_dir") or status.get("resolved_sim_dir")
    return {
        "paths": {key: str(value) if value else None for key, value in paths.items()},
        "status": status,
        "data_collection": data_collection,
        "sim_status": sim_status,
        "success_report": success_report,
        "patient_records": extract_patient_records(data_collection),
        "sim_dir": Path(sim_dir) if sim_dir else None,
    }


def write_runtime_effective_check(
    *,
    benchmark_output_root: Path,
    run_id: str,
    row: dict[str, Any],
    artifacts: dict[str, Any],
    patient_rows_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    sim_status = artifacts["sim_status"] if isinstance(artifacts["sim_status"], dict) else {}
    sim_resources = sim_status.get("resources", {}) if isinstance(sim_status, dict) else {}
    arrivals = sorted(
        minute for minute in (coerce_float(item.get("arrival_minute")) for item in patient_rows_payload) if minute is not None
    )
    ctas_distribution_observed: dict[str, int] = {}
    for item in patient_rows_payload:
        level = str(item.get("ctas_level") or "")
        if not level:
            continue
        ctas_distribution_observed[level] = ctas_distribution_observed.get(level, 0) + 1
    payload = {
        "run_id": run_id,
        "loaded_profile_path": str(REPO_ROOT / "configs" / "benchmark" / "large_tertiary_ed_profile.json"),
        "loaded_matrix_path": str(DEFAULT_SCENARIO_CSV),
        "loaded_scenario_row": row,
        "benchmark_basis": sim_resources.get("benchmark_basis") or row.get("benchmark_basis"),
        "standard_equivalent_patients_per_day": sim_resources.get("standard_equivalent_patients_per_day") or row.get("standard_equivalent_patients_per_day"),
        "actual_simulated_arrivals": sim_resources.get("actual_simulated_arrivals") or row.get("actual_simulated_arrivals"),
        "simulation_scale_factor": sim_resources.get("simulation_scale_factor") or row.get("simulation_scale_factor"),
        "run_steps": row.get("run_steps"),
        "seed": row.get("seed"),
        "arrival_schedule_patient_count": len(arrivals),
        "first_arrival_minute": arrivals[0] if arrivals else None,
        "last_arrival_minute": arrivals[-1] if arrivals else None,
        "burst_window_min": sim_resources.get("burst_window_min") or row.get("burst_window_min"),
        "ctas_distribution_observed": ctas_distribution_observed,
        "ctas_distribution_expected": parse_json_dict(row.get("ctas_mix")),
        "runtime_config_source_trace": {
            "scenario_status_path": artifacts["paths"].get("status"),
            "data_collection_path": artifacts["paths"].get("data_collection"),
            "sim_status_path": artifacts["paths"].get("sim_status"),
            "success_failure_report_path": artifacts["paths"].get("success_failure_report"),
            "resolved_sim_dir": artifacts["status"].get("sim_dir") or artifacts["status"].get("resolved_sim_dir"),
            "sim_status_resources_present": bool(sim_resources),
        },
    }
    run_path = benchmark_output_root / run_id / "runtime_effective_check.json"
    write_json(run_path, payload)
    aggregate_path = benchmark_output_root / "runtime_effective_check.json"
    aggregate = load_json(aggregate_path) if aggregate_path.exists() else {"runs": {}}
    aggregate.setdefault("runs", {})[run_id] = payload
    write_json(aggregate_path, aggregate)
    return payload


def ctas_level(record: dict[str, Any]) -> str | None:
    for key in ("ctas_level", "CTAS_score", "CTAS", "ctas"):
        value = record.get(key)
        if value in (None, "", 0, "0"):
            continue
        try:
            return f"L{int(float(value))}"
        except (TypeError, ValueError):
            text = str(value).upper()
            return text if text.startswith("L") else None
    return None


def first_available(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def terminal_state(record: dict[str, Any]) -> str:
    disposition = str(record.get("disposition_status") or "").strip()
    if disposition:
        return disposition
    state = str(record.get("state") or "").strip()
    if state:
        return state
    return "in_ed"


def transfer_summary_from_log(sim_dir: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sim_dir is None:
        return [], {"fullview_status": "not_available"}
    log_path = sim_dir / "analysis" / "transfer_requests.jsonl"
    if not log_path.exists():
        return [], {"fullview_status": "not_available"}
    events: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    by_type: dict[str, int] = {}
    accepted = 0
    rejected = 0
    for event in events:
        target = str(event.get("target_unit") or event.get("destination") or event.get("transfer_type") or "unknown")
        by_type[target] = by_type.get(target, 0) + 1
        status = str(event.get("status") or event.get("decision") or "").lower()
        if "accept" in status:
            accepted += 1
        if "reject" in status:
            rejected += 1
    total_decisions = accepted + rejected
    return events, {
        "fullview_status": "available",
        "transfer_requests_by_type": by_type,
        "fullview_accepted": accepted,
        "fullview_rejected": rejected,
        "fullview_accepted_rate": None if total_decisions == 0 else accepted / float(total_decisions),
    }


def _queue_pop_events(data_collection: Any) -> dict[str, dict[str, Any]]:
    first_by_patient: dict[str, dict[str, Any]] = {}
    if not isinstance(data_collection, dict):
        return first_by_patient
    bucket = data_collection.get("BedsideNurse") or {}
    if not isinstance(bucket, dict):
        return first_by_patient
    events: list[dict[str, Any]] = []
    for nurse_name, nurse_payload in bucket.items():
        if not isinstance(nurse_payload, dict):
            continue
        raw_events = nurse_payload.get("Queue_Pop_Events") or nurse_payload.get("Dispatch_Events") or []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            events.append(
                {
                    "step": event.get("step"),
                    "minute": event.get("minute"),
                    "patient": str(event.get("patient") or ""),
                    "nurse": str(event.get("nurse") or nurse_name),
                    "queue": event.get("queue"),
                    "assignment_path": event.get("assignment_path"),
                    "reserved_bed": event.get("reserved_bed"),
                }
            )
    events.sort(key=lambda item: (item.get("step") is None, item.get("step"), item.get("patient")))
    for event in events:
        patient = event["patient"]
        if patient and patient not in first_by_patient:
            first_by_patient[patient] = event
    return first_by_patient


def _doctor_assignment_events(data_collection: Any) -> dict[str, dict[str, Any]]:
    first_by_patient: dict[str, dict[str, Any]] = {}
    if not isinstance(data_collection, dict):
        return first_by_patient
    bucket = data_collection.get("Doctor") or {}
    if not isinstance(bucket, dict):
        return first_by_patient
    events: list[dict[str, Any]] = []
    for doctor_name, doctor_payload in bucket.items():
        if not isinstance(doctor_payload, dict):
            continue
        raw_events = doctor_payload.get("Doctor_Assignment_Events") or []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            events.append(
                {
                    "step": event.get("step"),
                    "patient": str(event.get("patient") or ""),
                    "doctor": str(event.get("doctor") or doctor_name),
                    "doctor_dispatch_policy": event.get("doctor_dispatch_policy"),
                }
            )
    events.sort(key=lambda item: (item.get("step") is None, item.get("step"), item.get("patient")))
    for event in events:
        patient = event["patient"]
        if patient and patient not in first_by_patient:
            first_by_patient[patient] = event
    return first_by_patient


def _queue_exposure_minutes(record: dict[str, Any], queue_name: str) -> float:
    payload = record.get("queue_exposure")
    if not isinstance(payload, dict):
        return 0.0
    queue_payload = payload.get(queue_name)
    if not isinstance(queue_payload, dict):
        return 0.0
    minutes = coerce_float(queue_payload.get("exposure_minutes"))
    return float(minutes or 0.0)


def _dominant_failure_stage(
    *,
    triage_complete_minute: float | None,
    queue_pop_minute: float | None,
    first_doctor_contact_minute: float | None,
    care_completed_minute: float | None,
    exit_minute: float | None,
    pia_sdr_success: bool | None,
) -> str:
    if triage_complete_minute is None:
        return "arrival_or_triage"
    if queue_pop_minute is None:
        return "pre_bedside_queue_or_zone_capacity"
    if first_doctor_contact_minute is None:
        return "doctor_first_contact_delay"
    if care_completed_minute is None:
        return "care_chain_not_completed"
    if exit_minute is None:
        return "exit_or_boarding_delay"
    if pia_sdr_success is False:
        return "pia_target_missed"
    return "completed"


def _failure_event(
    *,
    first_doctor_contact_minute: float | None,
    care_completed_minute: float | None,
    exit_minute: float | None,
    pia_sdr_success: bool | None,
) -> str:
    if first_doctor_contact_minute is None:
        return "no_doctor_contact"
    if pia_sdr_success is False:
        return "ctas_target_missed"
    if care_completed_minute is None:
        return "care_not_completed"
    if exit_minute is None:
        return "no_exit"
    return ""


def patient_rows(run_id: str, records: dict[str, dict[str, Any]], transfer_patients: set[str], data_collection: Any) -> list[dict[str, Any]]:
    queue_pop_by_patient = _queue_pop_events(data_collection)
    doctor_assign_by_patient = _doctor_assignment_events(data_collection)
    rows: list[dict[str, Any]] = []
    for patient_id, record in sorted(records.items()):
        level = ctas_level(record)
        arrival = coerce_float(first_available(record, "ed_arrival_minute", "ed_arrival_at"))
        triage_end = coerce_float(first_available(record, "triage_completed_minute", "triage_completed_at"))
        doctor_contact = coerce_float(first_available(record, "first_doctor_contact_minute", "first_doctor_contact_at"))
        care_completed = coerce_float(first_available(record, "care_completed_minute", "care_completed_at"))
        exit_minute = coerce_float(first_available(record, "ed_exit_minute", "ed_exit_at"))
        testing_kind = str(record.get("testing_kind") or "")
        queue_pop = queue_pop_by_patient.get(patient_id, {})
        queue_pop_minute = coerce_float(queue_pop.get("minute"))
        if queue_pop_minute is None and queue_pop.get("step") not in (None, ""):
            queue_pop_minute = float(queue_pop["step"])
        assigned_doctor = str(record.get("assigned_doctor") or (doctor_assign_by_patient.get(patient_id) or {}).get("doctor") or "")
        doctor_policy = str(
            record.get("doctor_dispatch_policy_at_contact")
            or (doctor_assign_by_patient.get(patient_id) or {}).get("doctor_dispatch_policy")
            or ""
        )
        arrival_to_triage = None if arrival is None or triage_end is None else triage_end - arrival
        triage_to_queue_pop = None if triage_end is None or queue_pop_minute is None else queue_pop_minute - triage_end
        queue_pop_to_doctor = None if queue_pop_minute is None or doctor_contact is None else doctor_contact - queue_pop_minute
        arrival_to_pia = None if arrival is None or doctor_contact is None else doctor_contact - arrival
        triage_to_pia = None if triage_end is None or doctor_contact is None else doctor_contact - triage_end
        doctor_to_complete = None if doctor_contact is None or care_completed is None else care_completed - doctor_contact
        arrival_to_exit = None if arrival is None or exit_minute is None else exit_minute - arrival
        target = CTAS_TARGET_MINUTES.get(level or "")
        pia_success = None if target is None or arrival_to_pia is None else arrival_to_pia <= target
        dominant_stage = _dominant_failure_stage(
            triage_complete_minute=triage_end,
            queue_pop_minute=queue_pop_minute,
            first_doctor_contact_minute=doctor_contact,
            care_completed_minute=care_completed,
            exit_minute=exit_minute,
            pia_sdr_success=pia_success,
        )
        failure_event = _failure_event(
            first_doctor_contact_minute=doctor_contact,
            care_completed_minute=care_completed,
            exit_minute=exit_minute,
            pia_sdr_success=pia_success,
        )
        bedside_exposure = _queue_exposure_minutes(record, "bedside_nurse")
        doctor_exposure = _queue_exposure_minutes(record, "doctor")
        queue_exposed = bedside_exposure > 30.0 or doctor_exposure > 30.0
        rows.append(
            {
                "run_id": run_id,
                "patient_id": patient_id,
                "encounter_id": record.get("encounter_id") or patient_id,
                "ctas_level": level or "",
                "arrival_minute": arrival if arrival is not None else "",
                "triage_complete_minute": triage_end if triage_end is not None else "",
                "queue_pop_minute": queue_pop_minute if queue_pop_minute is not None else "",
                "first_doctor_contact_minute": doctor_contact if doctor_contact is not None else "",
                "care_completed_minute": care_completed if care_completed is not None else "",
                "exit_minute": exit_minute if exit_minute is not None else "",
                "arrival_to_triage_min": arrival_to_triage if arrival_to_triage is not None else "",
                "triage_to_queue_pop_min": triage_to_queue_pop if triage_to_queue_pop is not None else "",
                "queue_pop_to_doctor_min": queue_pop_to_doctor if queue_pop_to_doctor is not None else "",
                "arrival_to_pia_min": arrival_to_pia if arrival_to_pia is not None else "",
                "triage_to_pia_min": triage_to_pia if triage_to_pia is not None else "",
                "doctor_to_care_complete_min": doctor_to_complete if doctor_to_complete is not None else "",
                "arrival_to_exit_min": arrival_to_exit if arrival_to_exit is not None else "",
                "pia_target_min": target if target is not None else "",
                "pia_sdr_success": pia_success if pia_success is not None else False,
                "failure_event": failure_event,
                "dominant_failure_stage": dominant_stage,
                "assigned_doctor": assigned_doctor,
                "doctor_dispatch_policy_at_contact": doctor_policy,
                "zone_assigned": record.get("injuries_zone") or "",
                "testing_kind": testing_kind,
                "final_state": terminal_state(record),
                "final_destination": record.get("disposition_target") or record.get("disposition_status") or "",
                "queue_exposed": queue_exposed,
                "bedside_nurse_exposure_minutes": bedside_exposure,
                "doctor_exposure_minutes": doctor_exposure,
            }
        )
    return rows


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    weight = rank - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def sdr_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row.get("ctas_level")]
    successes = [row for row in eligible if row.get("pia_sdr_success") is True]
    sdr_by_ctas: dict[str, float | None] = {}
    ptiles: dict[str, dict[str, float | None]] = {}
    for level in ("L1", "L2", "L3", "L4", "L5"):
        level_rows = [row for row in eligible if row.get("ctas_level") == level]
        level_success = [row for row in level_rows if row.get("pia_sdr_success") is True]
        sdr_by_ctas[level] = None if not level_rows else len(level_success) / float(len(level_rows))
        waits = [float(row["arrival_to_pia_min"]) for row in level_rows if row.get("arrival_to_pia_min") not in (None, "")]
        ptiles[level] = {
            "p50": percentile(waits, 0.5),
            "p90": percentile(waits, 0.9),
            "p95": percentile(waits, 0.95),
        }
    critical = [row for row in eligible if row.get("ctas_level") in {"L1", "L2"}]
    critical_success = [row for row in critical if row.get("pia_sdr_success") is True]
    l1_rows = [row for row in eligible if row.get("ctas_level") == "L1"]
    l1_rescue = [row for row in l1_rows if str(row.get("zone_assigned") or "").lower() in {"trauma room", "major injuries zone"}]
    return {
        "overall_sdr": None if not eligible else len(successes) / float(len(eligible)),
        "critical_sdr": None if not critical else len(critical_success) / float(len(critical)),
        "l1_rescue_routing_rate": None if not l1_rows else len(l1_rescue) / float(len(l1_rows)),
        "sdr_by_ctas": sdr_by_ctas,
        "arrival_to_pia_percentiles_by_ctas": ptiles,
    }


def capacity_timeseries(run_id: str, sim_dir: Path | None, sim_status: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    trace_path = sim_dir / "analysis" / "queue_trace_by_step.jsonl" if sim_dir else None
    if trace_path and trace_path.exists():
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                minute = coerce_int(payload.get("minute")) or coerce_int(payload.get("step")) or 0
                if minute % 5 != 0:
                    continue
                rescue = coerce_int(payload.get("trauma_room_occupied")) or 0
                high_acuity = coerce_int(payload.get("major_zone_occupied")) or 0
                observation = coerce_int(payload.get("minor_zone_occupied")) or 0
                total_beds = rescue + high_acuity + observation
                total_capacity = (
                    (coerce_int(payload.get("trauma_room_capacity")) or 0)
                    + (coerce_int(payload.get("major_zone_capacity")) or 0)
                    + (coerce_int(payload.get("minor_zone_capacity")) or 0)
                )
                occupancy_rate = None if total_capacity == 0 else total_beds / float(total_capacity)
                rows.append(
                    {
                        "run_id": run_id,
                        "sim_time_min": minute,
                        "active_patients": "",
                        "completed_patients": "",
                        "triage_queue_len": payload.get("triage_queue_len", 0),
                        "bed_queue_len": payload.get("bedside_nurse_waiting_len", 0),
                        "physician_queue_len": payload.get("doctor_queue_len", 0),
                        "diagnostic_queue_len": int(payload.get("lab_queue_len", 0) or 0)
                        + int(payload.get("imaging_queue_len", 0) or 0),
                        "occupied_rescue_beds": rescue,
                        "occupied_high_acuity_beds": high_acuity,
                        "occupied_observation_beds": observation,
                        "total_occupied_beds": total_beds,
                        "bed_occupancy_rate": occupancy_rate if occupancy_rate is not None else "",
                        "mean_physician_load": "",
                        "max_physician_load": "",
                        "nurse_busy_rate": "",
                        "current_arrival_rate_per_hour": "",
                    }
                )
    if rows:
        return rows
    queues = sim_status.get("queues", {}) if isinstance(sim_status, dict) else {}
    return [
        {
            "run_id": run_id,
            "sim_time_min": coerce_int(sim_status.get("step")) or 0,
            "active_patients": sim_status.get("current_patients", ""),
            "completed_patients": sim_status.get("completed", ""),
            "triage_queue_len": queues.get("triage", ""),
            "bed_queue_len": queues.get("bedside_nurse_waiting", ""),
            "physician_queue_len": queues.get("doctor_global", ""),
            "diagnostic_queue_len": int(queues.get("lab_waiting", 0) or 0) + int(queues.get("imaging_waiting", 0) or 0),
            "occupied_rescue_beds": "",
            "occupied_high_acuity_beds": "",
            "occupied_observation_beds": "",
            "total_occupied_beds": "",
            "bed_occupancy_rate": "",
            "mean_physician_load": "",
            "max_physician_load": "",
            "nurse_busy_rate": "",
            "current_arrival_rate_per_hour": "",
        }
    ]


def peak_value(rows: list[dict[str, Any]], key: str) -> int:
    values = [coerce_int(row.get(key)) or 0 for row in rows]
    return max(values) if values else 0


def main_bottleneck(timeseries: list[dict[str, Any]], success_report: dict[str, Any]) -> str:
    peak_triage = peak_value(timeseries, "triage_queue_len")
    peak_bed = peak_value(timeseries, "bed_queue_len")
    peak_physician = peak_value(timeseries, "physician_queue_len")
    peak_diagnostic = peak_value(timeseries, "diagnostic_queue_len")
    peaks = {
        "triage_capacity": peak_triage,
        "bed_capacity": peak_bed,
        "physician_capacity": peak_physician,
        "diagnostic_capacity": peak_diagnostic,
    }
    dominant = max(peaks, key=peaks.get)
    if peaks[dominant] <= 0:
        return "mixed_or_policy"
    return dominant


def scenario_config(row: dict[str, Any], sim_status: dict[str, Any]) -> dict[str, Any]:
    resources = sim_status.get("resources", {}) if isinstance(sim_status, dict) else {}
    return {
        "run_id": row["scenario_id"],
        "benchmark_basis": row.get("benchmark_basis") or "large_tertiary_ed_300_capacity_benchmark",
        "scenario_module": row.get("scenario_module"),
        "simulation_duration_min": coerce_int(row.get("run_steps")) or 1440,
        "random_seed": coerce_int(row.get("seed")) or 42,
        "standard_equivalent_patients_per_day": coerce_int(row.get("standard_equivalent_patients_per_day")),
        "actual_simulated_arrivals": coerce_int(row.get("actual_simulated_arrivals")),
        "simulation_scale_factor": coerce_float(row.get("simulation_scale_factor")),
        "load_multiplier": coerce_float(row.get("load_multiplier")),
        "burst_window_min": coerce_int(row.get("burst_window_min")),
        "equivalent_arrival_rate_per_hour": coerce_float(row.get("equivalent_arrival_rate_per_hour")),
        "ctas_mix": parse_json_dict(row.get("ctas_mix")),
        "physicians": coerce_int(row.get("physicians")) or coerce_int(row.get("doctor_count")),
        "triage_nurses": coerce_int(row.get("triage_nurses")) or coerce_int(row.get("triage_nurse_count")),
        "bedside_nurses": coerce_int(row.get("bedside_nurses")) or coerce_int(row.get("bedside_nurse_count")),
        "observation_beds": coerce_int(row.get("observation_beds")),
        "high_acuity_beds": coerce_int(row.get("high_acuity_beds")),
        "rescue_beds": coerce_int(row.get("rescue_beds")),
        "diagnostic_capacity": coerce_int(row.get("diagnostic_capacity")) or resources.get("imaging_capacity"),
        "resource_scaling_policy": row.get("resource_scaling_policy") or "unscaled_staff_scaled_patients",
        "notes": row.get("notes") or row.get("standard_resource_mapping_note") or "",
    }


def export_run(row: dict[str, Any], raw_output_root: Path, benchmark_output_root: Path) -> dict[str, Any]:
    run_id = str(row["scenario_id"])
    artifacts = extract_artifacts(raw_output_root, row)
    out_dir = benchmark_output_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    transfer_events, transfer_summary = transfer_summary_from_log(artifacts["sim_dir"])
    transfer_patients = {str(event.get("patient_id") or event.get("patient") or "") for event in transfer_events}
    patients = patient_rows(run_id, artifacts["patient_records"], transfer_patients, artifacts["data_collection"])
    write_json(out_dir / "raw_data_collection.json", artifacts["data_collection"])
    write_json(out_dir / "raw_sim_status.json", artifacts["sim_status"])
    write_json(out_dir / "raw_scenario_status.json", artifacts["status"])
    timeseries = capacity_timeseries(run_id, artifacts["sim_dir"], artifacts["sim_status"])
    sdr = sdr_summary(patients)
    success_report = artifacts["success_report"]
    completed_count = int(
        success_report.get("completed_care_count")
        or sum(1 for row_ in patients if row_.get("care_completed_minute") not in ("", None))
    )
    total_arrivals = len(patients)
    fullview_accepted_rate = transfer_summary.get("fullview_accepted_rate")
    summary = {
        "run_id": run_id,
        "scenario_module": row.get("scenario_module"),
        "total_arrivals": total_arrivals,
        "completed_count": completed_count,
        "lwbs_count": sum(1 for row_ in patients if row_.get("failure_event") == "left_without_being_seen"),
        "error_count": 0,
        "timeout_count": 0,
        "overall_sdr": sdr["overall_sdr"],
        "critical_sdr": sdr["critical_sdr"],
        "l1_rescue_routing_rate": sdr["l1_rescue_routing_rate"],
        "sdr_by_ctas": sdr["sdr_by_ctas"],
        "p50_arrival_to_pia_by_ctas": {k: v["p50"] for k, v in sdr["arrival_to_pia_percentiles_by_ctas"].items()},
        "p90_arrival_to_pia_by_ctas": {k: v["p90"] for k, v in sdr["arrival_to_pia_percentiles_by_ctas"].items()},
        "p95_arrival_to_pia_by_ctas": {k: v["p95"] for k, v in sdr["arrival_to_pia_percentiles_by_ctas"].items()},
        "peak_ed_census": peak_value(timeseries, "active_patients"),
        "peak_triage_queue": peak_value(timeseries, "triage_queue_len"),
        "peak_bed_queue": peak_value(timeseries, "bed_queue_len"),
        "peak_physician_queue": peak_value(timeseries, "physician_queue_len"),
        "peak_diagnostic_queue": peak_value(timeseries, "diagnostic_queue_len"),
        "peak_bed_occupancy_rate": max(
            [coerce_float(item.get("bed_occupancy_rate")) or 0.0 for item in timeseries],
            default=0.0,
        ),
        "recovery_time_min": None if row.get("scenario_module") != "burst_influx" else "not_available",
        "transfer_requests_by_type": transfer_summary.get("transfer_requests_by_type", {}),
        "fullview_accepted_rate": fullview_accepted_rate,
        "main_bottleneck": main_bottleneck(timeseries, success_report),
        "notes": row.get("notes") or "",
        "legacy_success_failure_report": success_report,
    }
    config = scenario_config(row, artifacts["sim_status"])
    write_json(out_dir / "scenario_config.json", config)
    write_csv(out_dir / "patient_level_results.csv", patients, PATIENT_COLUMNS)
    write_csv(out_dir / "capacity_timeseries.csv", timeseries, TIMESERIES_COLUMNS)
    write_json(out_dir / "run_summary.json", summary)
    write_json(
        screenshot_dir / "screenshot_status.json",
        {
            "screenshot_status": "not_available",
            "reason": "backend-only exporter does not capture dashboard screenshots",
            "required_before_ppt": True,
        },
    )
    flow_audit = build_flow_audit_for_run(row=row, raw_output_root=raw_output_root, benchmark_output_root=benchmark_output_root)
    write_json(out_dir / "flow_audit.json", flow_audit)
    runtime_effective = write_runtime_effective_check(
        benchmark_output_root=benchmark_output_root,
        run_id=run_id,
        row=row,
        artifacts=artifacts,
        patient_rows_payload=patients,
    )
    patient_trace_report = build_patient_trace(out_dir)
    ctas_priority_audit = audit_ctas_priority_run(out_dir)
    path_failure_audit = audit_path_failure_run(out_dir)
    bedside_bed_audit = audit_bedside_bed_run(out_dir)
    doctor_pia_audit = audit_doctor_pia_run(out_dir)
    return {
        **summary,
        "benchmark_output_dir": str(out_dir),
        "raw_output_dir": artifacts["paths"].get("output_dir"),
        "artifact_complete": bool(artifacts["paths"].get("data_collection") and artifacts["paths"].get("sim_status")),
        "flow_audit": flow_audit,
        "runtime_effective_check": runtime_effective,
        "patient_trace_report": patient_trace_report,
        "ctas_priority_audit": ctas_priority_audit,
        "path_failure_audit": path_failure_audit,
        "bedside_bed_audit": bedside_bed_audit,
        "doctor_pia_audit": doctor_pia_audit,
    }


def aggregate_runs(run_summaries: list[dict[str, Any]], benchmark_output_root: Path, rows: list[dict[str, Any]], raw_output_root: Path) -> None:
    aggregate_dir = benchmark_output_root / "aggregate"
    all_patients: list[dict[str, Any]] = []
    transfer_rows: list[dict[str, Any]] = []
    for summary in run_summaries:
        run_id = summary["run_id"]
        patient_path = benchmark_output_root / run_id / "patient_level_results.csv"
        if patient_path.exists():
            with patient_path.open("r", encoding="utf-8", newline="") as handle:
                all_patients.extend(csv.DictReader(handle))
        transfer_rows.append(
            {
                "run_id": run_id,
                "transfer_requests_by_type": json.dumps(summary.get("transfer_requests_by_type", {}), ensure_ascii=False),
                "fullview_accepted_rate": summary.get("fullview_accepted_rate"),
            }
        )

    summary_fields = [
        "run_id",
        "scenario_module",
        "total_arrivals",
        "completed_count",
        "overall_sdr",
        "critical_sdr",
        "l1_rescue_routing_rate",
        "peak_triage_queue",
        "peak_bed_queue",
        "peak_physician_queue",
        "peak_diagnostic_queue",
        "main_bottleneck",
        "artifact_complete",
        "benchmark_output_dir",
        "raw_output_dir",
    ]
    write_csv(aggregate_dir / "all_run_summary.csv", run_summaries, summary_fields)
    write_csv(aggregate_dir / "all_patient_level_results.csv", all_patients, PATIENT_COLUMNS)
    write_csv(aggregate_dir / "all_transfer_summary.csv", transfer_rows, ["run_id", "transfer_requests_by_type", "fullview_accepted_rate"])
    (aggregate_dir / "README_results_notes.md").write_text(
        "# Auto Capacity Benchmark Results Notes\n\n"
        "- Screenshot capture is not available in backend-only mode; see each run's screenshots/screenshot_status.json.\n"
        "- SDR is recomputed from patient-level records using Arrival-to-PIA targets from the benchmark specification.\n",
        encoding="utf-8",
    )
    write_flow_audit_aggregate(
        flow_results=[
            build_flow_audit_for_run(row=row, raw_output_root=raw_output_root, benchmark_output_root=benchmark_output_root)
            for row in rows
            if (benchmark_output_root / str(row["scenario_id"]) / "patient_level_results.csv").exists()
        ],
        benchmark_output_root=benchmark_output_root,
    )


def filter_rows(rows: Iterable[dict[str, Any]], run_ids: set[str] | None) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        run_id = str(row.get("scenario_id") or row.get("benchmark_run_id") or "")
        if not run_id:
            continue
        if run_ids is None or run_id in run_ids:
            selected.append(row)
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export EDMAS Auto Mode benchmark artifacts.")
    parser.add_argument("--scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--raw-output-root", default=str(DEFAULT_RAW_OUTPUT_ROOT))
    parser.add_argument("--benchmark-output-root", default=str(DEFAULT_BENCHMARK_OUTPUT_ROOT))
    parser.add_argument("--run-id", action="append", default=None, help="Export only the given run id; repeatable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_scenario_rows(Path(args.scenario_csv))
    selected = filter_rows(rows, set(args.run_id) if args.run_id else None)
    summaries = [
        export_run(
            row,
            raw_output_root=Path(args.raw_output_root),
            benchmark_output_root=Path(args.benchmark_output_root),
        )
        for row in selected
    ]
    aggregate_runs(summaries, Path(args.benchmark_output_root), selected, Path(args.raw_output_root))
    print(json.dumps({"exported_runs": [row["run_id"] for row in summaries], "count": len(summaries)}, indent=2))


if __name__ == "__main__":
    main()
