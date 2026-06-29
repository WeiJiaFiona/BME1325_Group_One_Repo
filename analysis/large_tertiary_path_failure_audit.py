#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _classify(event: dict[str, Any]) -> str:
    reason = str(event.get("failure_reason") or "")
    actor_role = str(event.get("actor_role") or "")
    intended = str(event.get("intended_action") or "").lower()
    if actor_role == "Doctor" and "persona" in reason:
        return "doctor_to_patient_no_path"
    if actor_role == "BedsideNurse" and "persona" in reason:
        return "nurse_to_patient_no_path"
    if actor_role == "Patient" and "bed" in intended:
        return "patient_to_bed_no_path"
    if actor_role == "Patient" and "exit" in intended:
        return "patient_to_exit_no_path"
    if actor_role == "Doctor" and "tile" in reason:
        return "bed_to_doctor_no_path"
    return "unknown_no_path"


def audit_run(run_dir: Path) -> dict[str, Any]:
    data_collection = _load_json(run_dir / "raw_data_collection.json")
    events = [event for event in (data_collection.get("Path_Failure_Events") or []) if isinstance(event, dict)] if isinstance(data_collection, dict) else []
    counter: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for event in events:
        category = _classify(event)
        counter[category] += 1
        rows.append(
            {
                "run_id": run_dir.name,
                "minute": event.get("minute"),
                "actor_id": event.get("actor_id"),
                "actor_role": event.get("actor_role"),
                "patient_id": event.get("patient_id"),
                "origin_tile": event.get("origin_tile"),
                "target_tile": event.get("target_tile"),
                "origin_zone": event.get("origin_zone"),
                "target_zone": event.get("target_zone"),
                "intended_action": event.get("intended_action"),
                "current_patient_state": event.get("current_patient_state"),
                "current_bed_id": event.get("current_bed_id"),
                "failure_reason": category,
                "raw_event_source": event.get("raw_event_source"),
            }
        )
    report = {
        "run_id": run_dir.name,
        "doctor_to_patient_no_path": counter["doctor_to_patient_no_path"],
        "nurse_to_patient_no_path": counter["nurse_to_patient_no_path"],
        "patient_to_bed_no_path": counter["patient_to_bed_no_path"],
        "patient_to_exit_no_path": counter["patient_to_exit_no_path"],
        "bed_to_doctor_no_path": counter["bed_to_doctor_no_path"],
        "unknown_no_path": counter["unknown_no_path"],
        "path_failure_event_count": len(rows),
        "telemetry_status": "ok" if rows else "limited_or_absent",
    }
    (run_dir / "path_failure_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "path_failure_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else ["run_id", "minute", "actor_id", "actor_role", "patient_id", "origin_tile", "target_tile", "origin_zone", "target_zone", "intended_action", "current_patient_state", "current_bed_id", "failure_reason", "raw_event_source"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit path failures for large tertiary benchmark runs.")
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
