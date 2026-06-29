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


DEFAULT_OUTPUT_CSV = REPO_ROOT / "configs" / "cluster" / "ed_bed_zone_capacity_sweep_scenarios.csv"
DEFAULT_SWEEP_OUTPUT_ROOT = "cluster_outputs/ed_bed_zone_capacity_sweep"

CAPACITY_FIELDS = [
    "major_zone_bed_multiplier",
    "minor_zone_capacity_multiplier",
    "observation_bed_multiplier",
    "downstream_ward_capacity_multiplier",
    "icu_acceptance_probability",
]


def _factor_label(value: float) -> str:
    return str(value).replace(".", "p")


def _base_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["experiment_group"] = "bed_zone_capacity_screening"
    payload["output_root"] = DEFAULT_SWEEP_OUTPUT_ROOT
    for field in CAPACITY_FIELDS:
        payload[field] = ""
    return payload


def build_capacity_sweep_rows(base_row: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(suffix: str, **overrides: Any) -> None:
        row = _base_payload(base_row)
        row.update(overrides)
        row["scenario_id"] = f"{base_row['scenario_id']}_capacity_{suffix}"
        rows.append(row)

    add("baseline")
    for multiplier in (1.25, 1.5, 2.0):
        add(f"major{_factor_label(multiplier)}", major_zone_bed_multiplier=multiplier)
    for multiplier in (1.25, 1.5):
        add(f"minor{_factor_label(multiplier)}", minor_zone_capacity_multiplier=multiplier)
    for multiplier in (1.5, 2.0):
        add(f"obs{_factor_label(multiplier)}", observation_bed_multiplier=multiplier)
    add("ward1p5", downstream_ward_capacity_multiplier=1.5)
    add("icu_accept_p1p0", icu_acceptance_probability=1.0)
    add("major1p5_minor1p5", major_zone_bed_multiplier=1.5, minor_zone_capacity_multiplier=1.5)
    add(
        "major2p0_minor1p5_ward1p5",
        major_zone_bed_multiplier=2.0,
        minor_zone_capacity_multiplier=1.5,
        downstream_ward_capacity_multiplier=1.5,
    )
    return rows


def write_capacity_sweep_csv(rows: list[dict[str, Any]], output_csv: str | Path) -> Path:
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
        *CAPACITY_FIELDS,
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ED bed/zone capacity screening scenario CSV.")
    parser.add_argument("--base-scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--base-row-index", type=int, default=22)
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_row = read_scenario_row(args.base_scenario_csv, int(args.base_row_index))
    output_path = write_capacity_sweep_csv(build_capacity_sweep_rows(base_row), args.output_csv)
    print(str(output_path))


if __name__ == "__main__":
    main()
