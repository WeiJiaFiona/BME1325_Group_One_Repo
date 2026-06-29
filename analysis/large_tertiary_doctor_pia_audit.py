#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")


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
    if not values:
        return None
    total = sum(values)
    if total == 0:
        return 0.0
    values = sorted(values)
    weighted = sum((index + 1) * value for index, value in enumerate(values))
    n = len(values)
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def audit_run(run_dir: Path) -> dict[str, Any]:
    rows = _read_csv(run_dir / "patient_level_results.csv")
    data_collection = _load_json(run_dir / "raw_data_collection.json")
    doctor_bucket = data_collection.get("Doctor", {}) if isinstance(data_collection, dict) else {}
    success_by_doctor: dict[str, int] = {}
    attempt_count = 0
    for doctor_name, payload in doctor_bucket.items() if isinstance(doctor_bucket, dict) else []:
        if not isinstance(payload, dict):
            continue
        events = [event for event in (payload.get("Doctor_Assignment_Events") or []) if isinstance(event, dict)]
        success_by_doctor[doctor_name] = len(events)
        attempt_count += len(events)
    queue_pop_to_doctor = [value for value in (_num(row.get("queue_pop_to_doctor_min")) for row in rows) if value is not None]
    by_level_zone: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"patients": 0, "no_doctor": 0, "doctor_contact": 0})
    for row in rows:
        key = (str(row.get("ctas_level") or ""), str(row.get("zone_assigned") or ""))
        by_level_zone[key]["patients"] += 1
        if row.get("first_doctor_contact_minute") in (None, ""):
            by_level_zone[key]["no_doctor"] += 1
        else:
            by_level_zone[key]["doctor_contact"] += 1
    report = {
        "run_id": run_dir.name,
        "doctor_assignment_attempt_count": attempt_count,
        "doctor_assignment_success_count": sum(success_by_doctor.values()),
        "doctor_assignment_success_rate": None if attempt_count == 0 else sum(success_by_doctor.values()) / float(attempt_count),
        "doctor_call_no_response_count": sum(1 for row in rows if str(row.get("assigned_doctor") or "").strip() and row.get("first_doctor_contact_minute") in (None, "")),
        "first_doctor_contact_count": sum(1 for row in rows if row.get("first_doctor_contact_minute") not in (None, "")),
        "no_doctor_contact_count": sum(1 for row in rows if row.get("first_doctor_contact_minute") in (None, "")),
        "no_doctor_contact_rate": None if not rows else sum(1 for row in rows if row.get("first_doctor_contact_minute") in (None, "")) / float(len(rows)),
        "queue_pop_to_doctor_p50": _percentile(queue_pop_to_doctor, 0.5),
        "queue_pop_to_doctor_p90": _percentile(queue_pop_to_doctor, 0.9),
        "doctor_workload_by_id": success_by_doctor,
        "doctor_workload_gini": _gini(list(success_by_doctor.values())),
        "patients_assigned_bed_no_doctor": [row.get("patient_id") for row in rows if row.get("queue_pop_minute") not in (None, "") and row.get("first_doctor_contact_minute") in (None, "")],
        "patients_stuck_after_doctor_contact": [row.get("patient_id") for row in rows if row.get("first_doctor_contact_minute") not in (None, "") and row.get("care_completed_minute") in (None, "")],
        "by_ctas_and_zone": [
            {
                "ctas_level": level,
                "zone": zone,
                "patient_count": payload["patients"],
                "no_doctor_contact_rate": None if payload["patients"] == 0 else payload["no_doctor"] / float(payload["patients"]),
                "doctor_contact_rate": None if payload["patients"] == 0 else payload["doctor_contact"] / float(payload["patients"]),
            }
            for (level, zone), payload in sorted(by_level_zone.items())
        ],
    }
    (run_dir / "doctor_pia_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "doctor_pia_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(report["by_ctas_and_zone"][0].keys()) if report["by_ctas_and_zone"] else ["ctas_level", "zone", "patient_count"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report["by_ctas_and_zone"])
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit doctor assignment and PIA for large tertiary benchmark runs.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", action="append", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.output_root)
    run_dirs = [root / run_id for run_id in args.run_id] if args.run_id else [path for path in root.iterdir() if path.is_dir() and path.name != "aggregate"]
    reports = [audit_run(run_dir) for run_dir in run_dirs if run_dir.exists()]
    print(json.dumps({"runs": [report["run_id"] for report in reports]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
