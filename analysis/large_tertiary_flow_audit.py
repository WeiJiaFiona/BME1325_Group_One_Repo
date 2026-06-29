#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
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


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    weight = rank - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _gini(values: list[int]) -> float | None:
    clean = [int(value) for value in values if int(value) >= 0]
    if not clean:
        return None
    total = sum(clean)
    if total == 0:
        return 0.0
    clean.sort()
    weighted_sum = 0
    for index, value in enumerate(clean, start=1):
        weighted_sum += index * value
    n = len(clean)
    return (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n


def _status_paths(output_root: Path) -> list[Path]:
    direct = output_root / "scenario_status.json"
    if direct.exists():
        return [direct]
    paths = sorted(output_root.glob("*/*/scenario_status.json"))
    if paths:
        return paths
    return sorted(output_root.glob("*/scenario_status.json"))


def _queue_trace_rows(sim_dir: Path | None) -> list[dict[str, Any]]:
    if sim_dir is None:
        return []
    path = sim_dir / "analysis" / "queue_trace_by_step.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _patient_bucket(data_collection: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data_collection, dict):
        return {}
    payload = data_collection.get("Patient", data_collection)
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}
    return {}


def _role_bucket(data_collection: Any, *keys: str) -> dict[str, Any]:
    if not isinstance(data_collection, dict):
        return {}
    for key in keys:
        payload = data_collection.get(key)
        if isinstance(payload, dict):
            return payload
    return {}


def _triage_workload(data_collection: Any) -> tuple[dict[str, int] | str, float | None]:
    bucket = _role_bucket(data_collection, "TriageNurse", "triage_nurse", "Triage Nurse")
    if not bucket:
        return "not_available", None
    workload = {
        nurse_name: len((payload.get("Patients_Attended") or [])) if isinstance(payload, dict) else 0
        for nurse_name, payload in bucket.items()
    }
    return workload, _gini(list(workload.values()))


def _bedside_bucket(data_collection: Any) -> dict[str, Any]:
    return _role_bucket(data_collection, "BedsideNurse", "bedside_nurse", "Bedside Nurse")


def _doctor_bucket(data_collection: Any) -> dict[str, Any]:
    return _role_bucket(data_collection, "Doctor", "doctor", "Doctors")


def _bedside_workload(data_collection: Any) -> tuple[dict[str, int], float | None]:
    bucket = _bedside_bucket(data_collection)
    workload: dict[str, int] = {}
    for nurse_name, payload in bucket.items():
        if not isinstance(payload, dict):
            workload[nurse_name] = 0
            continue
        queue_events = payload.get("Queue_Pop_Events") or payload.get("Dispatch_Events") or []
        workload[nurse_name] = sum(1 for event in queue_events if isinstance(event, dict))
    return workload, _gini(list(workload.values()))


def _doctor_workload(data_collection: Any) -> tuple[dict[str, int], float | None]:
    bucket = _doctor_bucket(data_collection)
    workload: dict[str, int] = {}
    for doctor_name, payload in bucket.items():
        if not isinstance(payload, dict):
            workload[doctor_name] = 0
            continue
        events = payload.get("Doctor_Assignment_Events") or []
        workload[doctor_name] = sum(1 for event in events if isinstance(event, dict))
    return workload, _gini(list(workload.values()))


def _bedside_scan_events(data_collection: Any) -> list[dict[str, Any]]:
    if not isinstance(data_collection, dict):
        return []
    return [event for event in (data_collection.get("Bedside_Queue_Scan_Events") or []) if isinstance(event, dict)]


def _repeat_patient_calls(data_collection: Any) -> int | str:
    bucket = _bedside_bucket(data_collection)
    if not bucket:
        return "not_available"
    counts: Counter[str] = Counter()
    for payload in bucket.values():
        if not isinstance(payload, dict):
            continue
        for entry in payload.get("Action_Log") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("action_type") == "GO_TO_PERSONA":
                target = str(entry.get("target_persona") or "").strip()
                if target:
                    counts[target] += 1
    return sum(count - 1 for count in counts.values() if count > 1)


def _top_reinsert_patients(patient_records: dict[str, dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    rows = []
    for patient_id, record in patient_records.items():
        count = int(_num(record.get("bedside_reinsert_count")) or 0)
        if count > 0:
            rows.append({"patient_id": patient_id, "bedside_reinsert_count": count})
    rows.sort(key=lambda item: (-item["bedside_reinsert_count"], item["patient_id"]))
    return len(rows), rows[:10]


def _peak(trace_rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_num(row.get(key)) for row in trace_rows]
    clean = [value for value in values if value is not None]
    return max(clean) if clean else None


def _first_non_null(values: list[Any]) -> Any:
    for value in values:
        if value not in (None, "", "not_available"):
            return value
    return None


def _resource_capacity(row: dict[str, Any]) -> dict[str, float | None]:
    return {
        "rescue": _num(row.get("rescue_beds")),
        "high_acuity": _num(row.get("high_acuity_beds")),
        "observation": _num(row.get("observation_beds")),
    }


def build_flow_audit_for_run(
    *,
    row: dict[str, Any],
    raw_output_root: Path,
    benchmark_output_root: Path,
) -> dict[str, Any]:
    scenario_id = str(row["scenario_id"])
    raw_dir = raw_output_root / str(row.get("experiment_group") or "") / scenario_id
    run_dir = benchmark_output_root / scenario_id
    status = _load_json(raw_dir / "scenario_status.json")
    sim_dir_value = status.get("sim_dir") or status.get("resolved_sim_dir")
    sim_dir = Path(sim_dir_value) if sim_dir_value else None
    data_collection = _load_json(raw_dir / "frozen_artifacts" / "data_collection.json")
    sim_status = _load_json(raw_dir / "frozen_artifacts" / "sim_status.json")
    patient_rows = _load_csv_rows(run_dir / "patient_level_results.csv")
    patient_records = _patient_bucket(data_collection)
    queue_trace_rows = _queue_trace_rows(sim_dir)
    scan_events = _bedside_scan_events(data_collection)
    triage_workload, triage_gini = _triage_workload(data_collection)
    bedside_workload, bedside_gini = _bedside_workload(data_collection)
    doctor_workload, doctor_gini = _doctor_workload(data_collection)
    reinsert_patient_count, top_reinsert = _top_reinsert_patients(patient_records)

    arrival_to_triage = [_num(item.get("arrival_to_triage_min")) for item in patient_rows]
    triage_to_queue_pop = [_num(item.get("triage_to_queue_pop_min")) for item in patient_rows]
    queue_pop_to_doctor = [_num(item.get("queue_pop_to_doctor_min")) for item in patient_rows]
    triage_to_pia = [_num(item.get("triage_to_pia_min")) for item in patient_rows]
    arrival_to_pia = [_num(item.get("arrival_to_pia_min")) for item in patient_rows]
    doctor_to_complete = [_num(item.get("doctor_to_care_complete_min")) for item in patient_rows]

    arrival_to_triage_clean = [value for value in arrival_to_triage if value is not None]
    triage_to_queue_pop_clean = [value for value in triage_to_queue_pop if value is not None]
    queue_pop_to_doctor_clean = [value for value in queue_pop_to_doctor if value is not None]
    triage_to_pia_clean = [value for value in triage_to_pia if value is not None]
    arrival_to_pia_clean = [value for value in arrival_to_pia if value is not None]
    doctor_to_complete_clean = [value for value in doctor_to_complete if value is not None]

    expected_arrivals = int(_num(row.get("actual_simulated_arrivals")) or 0)
    actual_arrivals = len(patient_rows)
    tolerance = max(2, int(round(expected_arrivals * 0.05))) if expected_arrivals else 0
    arrival_match = "match" if abs(actual_arrivals - expected_arrivals) <= tolerance else "mismatch"

    selected_count = sum(1 for event in scan_events if str(event.get("scan_result")) == "selected")
    reserve_bed_failed = sum(1 for event in scan_events if str(event.get("skip_reason")) == "reserve_bed_failed")
    zone_full = sum(1 for event in scan_events if str(event.get("skip_reason")) == "zone_full")
    empty_scan_count = sum(1 for event in scan_events if str(event.get("scan_result")) == "skipped")

    no_doctor_contact_count = sum(1 for item in patient_rows if item.get("first_doctor_contact_minute") in (None, ""))
    no_doctor_contact_rate = None if actual_arrivals == 0 else no_doctor_contact_count / float(actual_arrivals)
    doctor_assignment_count = sum(doctor_workload.values()) if isinstance(doctor_workload, dict) else 0
    doctor_assignment_success_rate = None
    if doctor_assignment_count > 0:
        doctor_assignment_success_rate = (actual_arrivals - no_doctor_contact_count) / float(doctor_assignment_count)

    lab_ordered_count = sum(1 for item in patient_rows if str(item.get("testing_kind") or "") == "lab")
    imaging_ordered_count = sum(1 for item in patient_rows if str(item.get("testing_kind") or "") == "imaging")
    treatment_started_count = sum(1 for item in patient_rows if item.get("first_doctor_contact_minute") not in (None, ""))
    care_completed_count = sum(1 for item in patient_rows if item.get("care_completed_minute") not in (None, ""))
    care_completion_rate = None if treatment_started_count == 0 else care_completed_count / float(treatment_started_count)

    stuck_in_triage_queue = [item["patient_id"] for item in patient_rows if item.get("triage_complete_minute") in (None, "")]
    stuck_in_bedside_queue = [
        item["patient_id"]
        for item in patient_rows
        if item.get("triage_complete_minute") not in (None, "") and item.get("queue_pop_minute") in (None, "")
    ]
    assigned_bed_no_doctor = [
        item["patient_id"]
        for item in patient_rows
        if item.get("queue_pop_minute") not in (None, "") and item.get("first_doctor_contact_minute") in (None, "")
    ]
    stuck_after_doctor = [
        item["patient_id"]
        for item in patient_rows
        if item.get("first_doctor_contact_minute") not in (None, "") and item.get("care_completed_minute") in (None, "")
    ]

    capacities = _resource_capacity(row)
    theoretical_bed_capacity = sum(value for value in capacities.values() if value is not None)
    trauma_capacity = _first_non_null(
        [
            _peak(queue_trace_rows, "trauma_room_capacity"),
            _num((((sim_status.get("zone_occupancy") or {}).get("trauma room") or {}).get("capacity"))),
        ]
    )
    major_capacity = _first_non_null(
        [
            _peak(queue_trace_rows, "major_zone_capacity"),
            _num((((sim_status.get("zone_occupancy") or {}).get("major injuries zone") or {}).get("capacity"))),
        ]
    )
    minor_capacity = _first_non_null(
        [
            _peak(queue_trace_rows, "minor_zone_capacity"),
            _num((((sim_status.get("zone_occupancy") or {}).get("minor injuries zone") or {}).get("capacity"))),
        ]
    )
    effective_bed_capacity = None
    if any(value is not None for value in [trauma_capacity, major_capacity, minor_capacity]):
        effective_bed_capacity = sum(value or 0 for value in [trauma_capacity, major_capacity, minor_capacity])
    effective_gap = None
    if theoretical_bed_capacity is not None and effective_bed_capacity is not None:
        effective_gap = theoretical_bed_capacity - effective_bed_capacity

    result = {
        "scenario_id": scenario_id,
        "benchmark_basis": row.get("benchmark_basis"),
        "scenario_module": row.get("scenario_module"),
        "run_dir": str(run_dir),
        "raw_dir": str(raw_dir),
        "arrival_triage": {
            "expected_arrivals": expected_arrivals,
            "actual_arrivals": actual_arrivals,
            "arrival_count_match_status": arrival_match,
            "triage_completion_rate": None if actual_arrivals == 0 else (actual_arrivals - len(stuck_in_triage_queue)) / float(actual_arrivals),
            "arrival_to_triage_p50": _percentile(arrival_to_triage_clean, 0.5),
            "arrival_to_triage_p90": _percentile(arrival_to_triage_clean, 0.9),
            "peak_triage_queue": _peak(queue_trace_rows, "triage_queue_len"),
            "triage_nurse_workload_by_id": triage_workload,
            "triage_nurse_workload_gini": triage_gini,
        },
        "bedside_queue": {
            "bedside_empty_scan_count": empty_scan_count if scan_events else "not_available",
            "bedside_selected_patient_count": selected_count if scan_events else len(triage_to_queue_pop_clean),
            "bedside_nurse_workload_by_id": bedside_workload,
            "bedside_nurse_workload_gini": bedside_gini,
            "repeated_patient_call_count": _repeat_patient_calls(data_collection),
            "reinsert_patient_count": reinsert_patient_count,
            "top_reinsert_patients": top_reinsert,
            "triage_to_queue_pop_p50": _percentile(triage_to_queue_pop_clean, 0.5),
            "triage_to_queue_pop_p90": _percentile(triage_to_queue_pop_clean, 0.9),
            "reserve_bed_failed_count": reserve_bed_failed if scan_events else "not_available",
            "zone_full_count": zone_full if scan_events else "not_available",
        },
        "patient_state": {
            "stuck_patient_count": len(set(stuck_in_triage_queue + stuck_in_bedside_queue + assigned_bed_no_doctor + stuck_after_doctor)),
            "patients_stuck_in_triage_queue": stuck_in_triage_queue[:25],
            "patients_stuck_in_bedside_queue": stuck_in_bedside_queue[:25],
            "patients_assigned_bed_no_doctor": assigned_bed_no_doctor[:25],
            "patients_with_duplicate_active_state": "not_available",
        },
        "doctor_pia": {
            "doctor_assignment_count": doctor_assignment_count,
            "doctor_assignment_success_rate": doctor_assignment_success_rate,
            "doctor_workload_by_id": doctor_workload,
            "doctor_workload_gini": doctor_gini,
            "doctor_call_patient_no_response_count": sum(
                1
                for item in patient_rows
                if str(item.get("assigned_doctor") or "").strip() and item.get("first_doctor_contact_minute") in (None, "")
            ),
            "no_doctor_contact_count": no_doctor_contact_count,
            "no_doctor_contact_rate": no_doctor_contact_rate,
            "queue_pop_to_doctor_p50": _percentile(queue_pop_to_doctor_clean, 0.5),
            "queue_pop_to_doctor_p90": _percentile(queue_pop_to_doctor_clean, 0.9),
            "triage_to_pia_p50": _percentile(triage_to_pia_clean, 0.5),
            "triage_to_pia_p90": _percentile(triage_to_pia_clean, 0.9),
            "arrival_to_pia_p50": _percentile(arrival_to_pia_clean, 0.5),
            "arrival_to_pia_p90": _percentile(arrival_to_pia_clean, 0.9),
        },
        "care_chain": {
            "lab_ordered_count": lab_ordered_count,
            "imaging_ordered_count": imaging_ordered_count,
            "treatment_started_count": treatment_started_count,
            "care_completed_count": care_completed_count,
            "care_completion_rate": care_completion_rate,
            "doctor_to_care_complete_p50": _percentile(doctor_to_complete_clean, 0.5),
            "doctor_to_care_complete_p90": _percentile(doctor_to_complete_clean, 0.9),
            "patients_stuck_after_doctor_contact": stuck_after_doctor[:25],
        },
        "spatial_occupancy": {
            "no_path_possible_count": "not_available",
            "spatial_coupling_bug_count": "not_available",
            "doctor_bed_tile_conflict_count": "not_available",
            "nurse_path_blocked_count": "not_available",
            "theoretical_bed_capacity": theoretical_bed_capacity,
            "effective_bed_capacity": effective_bed_capacity,
            "effective_capacity_gap": effective_gap,
            "major_zone_peak_occupancy": _peak(queue_trace_rows, "major_zone_occupied"),
            "minor_zone_peak_occupancy": _peak(queue_trace_rows, "minor_zone_occupied"),
            "resus_peak_occupancy": _peak(queue_trace_rows, "trauma_room_occupied"),
        },
        "evidence_limitations": [
            "triage_nurse_workload_by_id requires new triage telemetry if bucket is not populated",
            "spatial/path conflict counts are not structurally logged yet",
        ],
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "flow_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def write_flow_audit_aggregate(
    *,
    flow_results: list[dict[str, Any]],
    benchmark_output_root: Path,
) -> None:
    aggregate_dir = benchmark_output_root / "aggregate"
    aggregate_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario_id",
        "benchmark_basis",
        "scenario_module",
        "expected_arrivals",
        "actual_arrivals",
        "arrival_count_match_status",
        "triage_completion_rate",
        "peak_triage_queue",
        "triage_nurse_workload_gini",
        "bedside_selected_patient_count",
        "bedside_nurse_workload_gini",
        "repeated_patient_call_count",
        "reinsert_patient_count",
        "reserve_bed_failed_count",
        "zone_full_count",
        "doctor_assignment_count",
        "doctor_assignment_success_rate",
        "doctor_workload_gini",
        "no_doctor_contact_count",
        "no_doctor_contact_rate",
        "triage_to_queue_pop_p90",
        "queue_pop_to_doctor_p90",
        "triage_to_pia_p90",
        "arrival_to_pia_p90",
        "care_completion_rate",
        "doctor_to_care_complete_p90",
        "stuck_patient_count",
        "theoretical_bed_capacity",
        "effective_bed_capacity",
        "effective_capacity_gap",
        "major_zone_peak_occupancy",
        "minor_zone_peak_occupancy",
        "resus_peak_occupancy",
    ]
    rows = []
    for item in flow_results:
        rows.append(
            {
                "scenario_id": item["scenario_id"],
                "benchmark_basis": item.get("benchmark_basis"),
                "scenario_module": item.get("scenario_module"),
                "expected_arrivals": item["arrival_triage"]["expected_arrivals"],
                "actual_arrivals": item["arrival_triage"]["actual_arrivals"],
                "arrival_count_match_status": item["arrival_triage"]["arrival_count_match_status"],
                "triage_completion_rate": item["arrival_triage"]["triage_completion_rate"],
                "peak_triage_queue": item["arrival_triage"]["peak_triage_queue"],
                "triage_nurse_workload_gini": item["arrival_triage"]["triage_nurse_workload_gini"],
                "bedside_selected_patient_count": item["bedside_queue"]["bedside_selected_patient_count"],
                "bedside_nurse_workload_gini": item["bedside_queue"]["bedside_nurse_workload_gini"],
                "repeated_patient_call_count": item["bedside_queue"]["repeated_patient_call_count"],
                "reinsert_patient_count": item["bedside_queue"]["reinsert_patient_count"],
                "reserve_bed_failed_count": item["bedside_queue"]["reserve_bed_failed_count"],
                "zone_full_count": item["bedside_queue"]["zone_full_count"],
                "doctor_assignment_count": item["doctor_pia"]["doctor_assignment_count"],
                "doctor_assignment_success_rate": item["doctor_pia"]["doctor_assignment_success_rate"],
                "doctor_workload_gini": item["doctor_pia"]["doctor_workload_gini"],
                "no_doctor_contact_count": item["doctor_pia"]["no_doctor_contact_count"],
                "no_doctor_contact_rate": item["doctor_pia"]["no_doctor_contact_rate"],
                "triage_to_queue_pop_p90": item["bedside_queue"]["triage_to_queue_pop_p90"],
                "queue_pop_to_doctor_p90": item["doctor_pia"]["queue_pop_to_doctor_p90"],
                "triage_to_pia_p90": item["doctor_pia"]["triage_to_pia_p90"],
                "arrival_to_pia_p90": item["doctor_pia"]["arrival_to_pia_p90"],
                "care_completion_rate": item["care_chain"]["care_completion_rate"],
                "doctor_to_care_complete_p90": item["care_chain"]["doctor_to_care_complete_p90"],
                "stuck_patient_count": item["patient_state"]["stuck_patient_count"],
                "theoretical_bed_capacity": item["spatial_occupancy"]["theoretical_bed_capacity"],
                "effective_bed_capacity": item["spatial_occupancy"]["effective_bed_capacity"],
                "effective_capacity_gap": item["spatial_occupancy"]["effective_capacity_gap"],
                "major_zone_peak_occupancy": item["spatial_occupancy"]["major_zone_peak_occupancy"],
                "minor_zone_peak_occupancy": item["spatial_occupancy"]["minor_zone_peak_occupancy"],
                "resus_peak_occupancy": item["spatial_occupancy"]["resus_peak_occupancy"],
            }
        )
    with (aggregate_dir / "all_flow_audit_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_all_flow_audits(
    *,
    scenario_csv: Path,
    raw_output_root: Path,
    benchmark_output_root: Path,
    run_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows = _load_rows(scenario_csv)
    selected = [row for row in rows if run_ids is None or str(row.get("scenario_id")) in run_ids]
    flow_results = [
        build_flow_audit_for_run(row=row, raw_output_root=raw_output_root, benchmark_output_root=benchmark_output_root)
        for row in selected
        if (benchmark_output_root / str(row["scenario_id"]) / "patient_level_results.csv").exists()
    ]
    write_flow_audit_aggregate(flow_results=flow_results, benchmark_output_root=benchmark_output_root)
    return flow_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build large tertiary flow audits from exported benchmark runs.")
    parser.add_argument("--scenario-csv", required=True)
    parser.add_argument("--raw-output-root", required=True)
    parser.add_argument("--benchmark-output-root", required=True)
    parser.add_argument("--run-id", action="append", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = build_all_flow_audits(
        scenario_csv=Path(args.scenario_csv),
        raw_output_root=Path(args.raw_output_root),
        benchmark_output_root=Path(args.benchmark_output_root),
        run_ids=set(args.run_id) if args.run_id else None,
    )
    print(json.dumps({"flow_audits": [item["scenario_id"] for item in results], "count": len(results)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
