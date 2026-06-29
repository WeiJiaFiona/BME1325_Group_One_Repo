#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
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
    scan_events = [event for event in (data_collection.get("Bedside_Queue_Scan_Events") or []) if isinstance(event, dict)] if isinstance(data_collection, dict) else []
    bedside_bucket = data_collection.get("BedsideNurse", {}) if isinstance(data_collection, dict) else {}
    workload: dict[str, int] = {}
    queue_pop_count = 0
    repeated_call_count = 0
    for nurse_name, payload in bedside_bucket.items() if isinstance(bedside_bucket, dict) else []:
        if not isinstance(payload, dict):
            continue
        queue_events = [event for event in (payload.get("Queue_Pop_Events") or payload.get("Dispatch_Events") or []) if isinstance(event, dict)]
        queue_pop_count += len(queue_events)
        workload[nurse_name] = len(queue_events)
        repeated_call_count += sum(1 for event in (payload.get("Action_Log") or []) if isinstance(event, dict) and event.get("action_type") == "GO_TO_PERSONA")
    triage_to_queue = [value for value in (_num(row.get("triage_to_queue_pop_min")) for row in rows) if value is not None]

    report = {
        "run_id": run_dir.name,
        "bedside_queue_entered_count": sum(1 for row in rows if row.get("triage_complete_minute") not in (None, "")),
        "queue_pop_count": queue_pop_count,
        "repeated_call_count": repeated_call_count,
        "reinsert_count": sum(1 for row in rows if row.get("dominant_failure_stage") == "pre_bedside_queue_or_zone_capacity"),
        "reserve_bed_attempt_count": sum(1 for event in scan_events if str(event.get("scan_result") or "") in {"selected", "skipped"}),
        "reserve_bed_success_count": sum(1 for event in scan_events if str(event.get("scan_result") or "") == "selected"),
        "reserve_bed_failed_count": sum(1 for event in scan_events if str(event.get("skip_reason") or "") == "reserve_bed_failed"),
        "zone_full_count": sum(1 for event in scan_events if str(event.get("skip_reason") or "") == "zone_full"),
        "bed_assigned_count": sum(1 for row in rows if row.get("queue_pop_minute") not in (None, "")),
        "bed_assigned_but_no_doctor_count": sum(1 for row in rows if row.get("queue_pop_minute") not in (None, "") and row.get("first_doctor_contact_minute") in (None, "")),
        "triage_to_queue_pop_p50": _percentile(triage_to_queue, 0.5),
        "triage_to_queue_pop_p90": _percentile(triage_to_queue, 0.9),
        "bed_assignment_delay_p50": _percentile(triage_to_queue, 0.5),
        "bed_assignment_delay_p90": _percentile(triage_to_queue, 0.9),
        "bedside_nurse_workload_by_id": workload,
        "bedside_nurse_workload_gini": _gini(list(workload.values())),
        "telemetry_status": "ok" if scan_events or workload else "limited",
    }
    (run_dir / "bedside_bed_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "bedside_bed_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report.keys()))
        writer.writeheader()
        writer.writerow(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit bedside queue and bed assignment for large tertiary benchmark runs.")
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
