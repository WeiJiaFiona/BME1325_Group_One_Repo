#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.cluster.run_one_ed_bottleneck_v1_scenario import DEFAULT_SCENARIO_CSV, read_scenario_row


DEFAULT_OUTPUT_CSV = REPO_ROOT / "configs" / "cluster" / "ed_doctor_stage_sweep_scenarios.csv"
DEFAULT_SWEEP_OUTPUT_ROOT = "cluster_outputs/ed_doctor_stage_sweep"

EXTRA_FIELDS = [
    "major_zone_bed_multiplier",
    "minor_zone_capacity_multiplier",
    "observation_bed_multiplier",
    "downstream_ward_capacity_multiplier",
    "icu_acceptance_probability",
    "doctor_count_override",
    "doctor_count_delta",
    "doctor_dispatch_policy",
]


def _base_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["experiment_group"] = "doctor_stage_sweep"
    payload["output_root"] = DEFAULT_SWEEP_OUTPUT_ROOT
    payload["major_zone_bed_multiplier"] = 1.5
    payload["minor_zone_capacity_multiplier"] = 1.5
    for field in EXTRA_FIELDS:
        payload.setdefault(field, "")
    return payload


def build_doctor_stage_sweep_rows(base_row: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(suffix: str, **overrides: Any) -> None:
        row = _base_payload(base_row)
        row.update(overrides)
        row["scenario_id"] = f"{base_row['scenario_id']}_capacity_major1p5_minor1p5_doctor_{suffix}"
        rows.append(row)

    add("baseline_calibrated")
    add("plus_1", doctor_count_delta=1)
    add("plus_2", doctor_count_delta=2)
    add("plus_4", doctor_count_delta=4)
    add("dispatch_fifo", doctor_dispatch_policy="fifo")
    add("dispatch_ctas_priority", doctor_dispatch_policy="ctas_priority")
    add("dispatch_oldest_wait_first", doctor_dispatch_policy="oldest_wait_first")
    add("plus_2_ctas_priority", doctor_count_delta=2, doctor_dispatch_policy="ctas_priority")
    add("plus_2_oldest_wait_first", doctor_count_delta=2, doctor_dispatch_policy="oldest_wait_first")
    return rows


def write_doctor_stage_sweep_csv(rows: list[dict[str, Any]], output_csv: str | Path) -> Path:
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario_id",
        "hospital_profile",
        "load_factor",
        "run_steps",
        "seed",
        "doctor_count",
        "nurse_count_total",
        "triage_nurse_count",
        "bedside_nurse_count",
        "bedside_nurse_service_time_multiplier",
        "low_ctas_fast_track_enabled",
        "low_ctas_fast_track_fraction",
        "experiment_group",
        "output_root",
        *EXTRA_FIELDS,
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ED doctor-stage sweep scenario CSV.")
    parser.add_argument("--base-scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--base-row-index", type=int, default=22)
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_row = read_scenario_row(args.base_scenario_csv, int(args.base_row_index))
    output_path = write_doctor_stage_sweep_csv(build_doctor_stage_sweep_rows(base_row), args.output_csv)
    print(str(output_path))


if __name__ == "__main__":
    main()

