#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")
LEVELS = ["L1", "L2", "L3", "L4", "L5"]


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


def _stats(rows: list[dict[str, Any]], field: str) -> tuple[float | None, float | None]:
    clean = [value for value in (_num(row.get(field)) for row in rows) if value is not None]
    return _percentile(clean, 0.5), _percentile(clean, 0.9)


def audit_run(run_dir: Path) -> dict[str, Any]:
    rows = _read_csv(run_dir / "patient_level_results.csv")
    by_level: list[dict[str, Any]] = []
    l4_p50 = _percentile([value for value in (_num(row.get("arrival_to_pia_min")) for row in rows if row.get("ctas_level") == "L4") if value is not None], 0.5)

    for level in LEVELS:
        level_rows = [row for row in rows if row.get("ctas_level") == level]
        patient_count = len(level_rows)
        arrival_to_triage_p50, arrival_to_triage_p90 = _stats(level_rows, "arrival_to_triage_min")
        triage_to_queue_pop_p50, triage_to_queue_pop_p90 = _stats(level_rows, "triage_to_queue_pop_min")
        queue_pop_to_doctor_p50, queue_pop_to_doctor_p90 = _stats(level_rows, "queue_pop_to_doctor_min")
        arrival_to_pia_p50, arrival_to_pia_p90 = _stats(level_rows, "arrival_to_pia_min")
        no_doctor = sum(1 for row in level_rows if row.get("first_doctor_contact_minute") in (None, ""))
        bed_assigned = sum(1 for row in level_rows if row.get("queue_pop_minute") not in (None, ""))
        doctor_assigned = sum(1 for row in level_rows if str(row.get("assigned_doctor") or "").strip())
        pia_success = sum(1 for row in level_rows if str(row.get("pia_sdr_success")).lower() == "true")
        by_level.append(
            {
                "ctas_level": level,
                "patient_count": patient_count,
                "arrival_to_triage_p50": arrival_to_triage_p50,
                "arrival_to_triage_p90": arrival_to_triage_p90,
                "triage_to_queue_pop_p50": triage_to_queue_pop_p50,
                "triage_to_queue_pop_p90": triage_to_queue_pop_p90,
                "queue_pop_to_doctor_p50": queue_pop_to_doctor_p50,
                "queue_pop_to_doctor_p90": queue_pop_to_doctor_p90,
                "arrival_to_pia_p50": arrival_to_pia_p50,
                "arrival_to_pia_p90": arrival_to_pia_p90,
                "no_doctor_contact_rate": None if patient_count == 0 else no_doctor / float(patient_count),
                "bed_assigned_rate": None if patient_count == 0 else bed_assigned / float(patient_count),
                "doctor_assignment_success_rate": None if patient_count == 0 else doctor_assigned / float(patient_count),
                "pia_sdr": None if patient_count == 0 else pia_success / float(patient_count),
            }
        )

    ctas1_wait_longer_than_ctas4_count = 0
    ctas2_wait_longer_than_ctas4_count = 0
    if l4_p50 is not None:
        for row in rows:
            wait = _num(row.get("arrival_to_pia_min"))
            if wait is None:
                continue
            if row.get("ctas_level") == "L1" and wait > l4_p50:
                ctas1_wait_longer_than_ctas4_count += 1
            if row.get("ctas_level") == "L2" and wait > l4_p50:
                ctas2_wait_longer_than_ctas4_count += 1
    ctas1_no_contact_count = sum(1 for row in rows if row.get("ctas_level") == "L1" and row.get("first_doctor_contact_minute") in (None, ""))
    ctas2_no_contact_count = sum(1 for row in rows if row.get("ctas_level") == "L2" and row.get("first_doctor_contact_minute") in (None, ""))
    critical_total = sum(1 for row in rows if row.get("ctas_level") in {"L1", "L2"})
    inversion_total = ctas1_wait_longer_than_ctas4_count + ctas2_wait_longer_than_ctas4_count + ctas1_no_contact_count + ctas2_no_contact_count

    report = {
        "run_id": run_dir.name,
        "by_ctas_level": by_level,
        "ctas1_wait_longer_than_ctas4_count": ctas1_wait_longer_than_ctas4_count,
        "ctas2_wait_longer_than_ctas4_count": ctas2_wait_longer_than_ctas4_count,
        "ctas1_no_contact_count": ctas1_no_contact_count,
        "ctas2_no_contact_count": ctas2_no_contact_count,
        "critical_priority_inversion_rate": None if critical_total == 0 else inversion_total / float(critical_total),
        "priority_discipline_failure": inversion_total > 0,
        "priority_inversion_rule": "L1/L2 arrival_to_pia compared against L4 arrival_to_pia p50 plus no_doctor_contact counts",
    }
    (run_dir / "ctas_priority_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "ctas_priority_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(by_level[0].keys()) if by_level else ["ctas_level"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(by_level)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CTAS priority discipline for large tertiary benchmark runs.")
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
