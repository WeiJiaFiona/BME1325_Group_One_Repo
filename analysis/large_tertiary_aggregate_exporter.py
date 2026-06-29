#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def aggregate(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    run_dirs = [p for p in output_root.iterdir() if p.is_dir() and p.name != "aggregate"] if output_root.exists() else []
    run_rows: list[dict[str, Any]] = []
    patient_rows: list[dict[str, Any]] = []
    bottleneck_rows: list[dict[str, Any]] = []
    for run_dir in sorted(run_dirs):
        summary = _load_json(run_dir / "run_summary.json")
        validation = _load_json(run_dir / "validator_report.json")
        bottleneck = _load_json(run_dir / "bottleneck_audit.json")
        if summary:
            run_rows.append(
                {
                    "run_id": summary.get("run_id", run_dir.name),
                    "scenario_module": summary.get("scenario_module"),
                    "standard_equivalent_patients_per_day": summary.get("standard_equivalent_patients_per_day"),
                    "actual_simulated_arrivals": summary.get("actual_simulated_arrivals"),
                    "overall_sdr": summary.get("overall_sdr"),
                    "critical_sdr": summary.get("critical_sdr"),
                    "completed_count": summary.get("completed_count"),
                    "peak_triage_queue": summary.get("peak_triage_queue"),
                    "peak_bed_queue": summary.get("peak_bed_queue"),
                    "peak_physician_queue": summary.get("peak_physician_queue"),
                    "peak_diagnostic_queue": summary.get("peak_diagnostic_queue"),
                    "main_bottleneck": summary.get("main_bottleneck"),
                    "validation_status": validation.get("validation_status"),
                    "bug_status": summary.get("bug_status"),
                }
            )
        for patient in _read_csv(run_dir / "patient_level_results.csv"):
            patient["run_id"] = patient.get("run_id") or run_dir.name
            patient_rows.append(patient)
        if bottleneck:
            bottleneck_rows.append(
                {
                    "run_id": bottleneck.get("run_id", run_dir.name),
                    "main_bottleneck": bottleneck.get("main_bottleneck"),
                    "candidate_bottlenecks": json.dumps(bottleneck.get("candidate_bottlenecks", []), ensure_ascii=False),
                    "bottleneck_evidence": json.dumps(bottleneck.get("bottleneck_evidence", []), ensure_ascii=False),
                    "telemetry_status": bottleneck.get("telemetry_status"),
                }
            )
    aggregate_dir = output_root / "aggregate"
    _write_csv(
        aggregate_dir / "all_run_summary.csv",
        run_rows,
        [
            "run_id",
            "scenario_module",
            "standard_equivalent_patients_per_day",
            "actual_simulated_arrivals",
            "overall_sdr",
            "critical_sdr",
            "completed_count",
            "peak_triage_queue",
            "peak_bed_queue",
            "peak_physician_queue",
            "peak_diagnostic_queue",
            "main_bottleneck",
            "validation_status",
            "bug_status",
        ],
    )
    patient_fields = list(patient_rows[0].keys()) if patient_rows else ["run_id"]
    _write_csv(aggregate_dir / "all_patient_level_results.csv", patient_rows, patient_fields)
    _write_csv(
        aggregate_dir / "all_bottleneck_summary.csv",
        bottleneck_rows,
        ["run_id", "main_bottleneck", "candidate_bottlenecks", "bottleneck_evidence", "telemetry_status"],
    )
    (aggregate_dir / "README_results_notes.md").write_text(
        "# Large Tertiary Benchmark Aggregate Notes\n\n"
        "- SDR fields are recomputed from patient-level output by validator_report.json.\n"
        "- Resources marked metadata_only must not be interpreted as runtime-effective capacity.\n"
        "- Placeholder screenshots are not acceptable for final PPT evidence.\n",
        encoding="utf-8",
    )
    return {"run_count": len(run_rows), "patient_count": len(patient_rows), "bottleneck_count": len(bottleneck_rows)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate large tertiary benchmark outputs.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = aggregate(Path(args.output_root))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
