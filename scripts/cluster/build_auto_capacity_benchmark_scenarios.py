#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "configs" / "cluster" / "auto_capacity_cn_benchmark_scenarios.csv"

N_SIM_1X = 100
STANDARD_EQ_1X = 300
BASELINE_PROFILE_NORMAL_PATIENTS = 64
SEED = 42
RUN_STEPS = 1440

BASELINE_CTAS_MIX = {"L1": 0.059, "L2": 0.393, "L3": 0.415, "L4": 0.109, "L5": 0.024}
CRITICAL_MIXES = {
    "C_CRIT_45_seed42": BASELINE_CTAS_MIX,
    "C_CRIT_50_seed42": {"L1": 0.08, "L2": 0.42, "L3": 0.38, "L4": 0.10, "L5": 0.02},
    "C_CRIT_55_seed42": {"L1": 0.10, "L2": 0.45, "L3": 0.34, "L4": 0.09, "L5": 0.02},
    "C_CRIT_60_seed42": {"L1": 0.12, "L2": 0.48, "L3": 0.31, "L4": 0.07, "L5": 0.02},
    "C_CRIT_70_seed42": {"L1": 0.15, "L2": 0.55, "L3": 0.25, "L4": 0.04, "L5": 0.01},
    "C_CRIT_80_seed42": {"L1": 0.20, "L2": 0.60, "L3": 0.17, "L4": 0.02, "L5": 0.01},
}

FIELDNAMES = [
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
    "major_zone_bed_multiplier",
    "minor_zone_capacity_multiplier",
    "observation_bed_multiplier",
    "downstream_ward_capacity_multiplier",
    "icu_acceptance_probability",
    "doctor_count_override",
    "doctor_count_delta",
    "doctor_dispatch_policy",
    "benchmark_run_id",
    "benchmark_basis",
    "scenario_module",
    "standard_equivalent_patients_per_day",
    "actual_simulated_arrivals",
    "simulation_scale_factor",
    "load_multiplier",
    "arrival_profile_mode",
    "burst_window_min",
    "equivalent_arrival_rate_per_hour",
    "ctas_mix",
    "resource_scaling_policy",
    "physicians",
    "triage_nurses",
    "bedside_nurses",
    "observation_beds",
    "high_acuity_beds",
    "rescue_beds",
    "diagnostic_capacity",
    "standard_resource_mapping_note",
    "notes",
]


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _base_row(run_id: str, module: str, *, actual_arrivals: int, standard_equivalent: int) -> dict[str, Any]:
    load_factor = actual_arrivals / float(BASELINE_PROFILE_NORMAL_PATIENTS)
    return {
        "scenario_id": run_id,
        "hospital_profile": "large_tertiary_ed",
        "load_factor": f"{load_factor:.8f}",
        "run_steps": RUN_STEPS,
        "seed": SEED,
        "doctor_count": 10,
        "nurse_count_total": 27,
        "triage_nurse_count": 3,
        "bedside_nurse_count": 24,
        "bedside_nurse_service_time_multiplier": 1.0,
        "low_ctas_fast_track_enabled": "False",
        "low_ctas_fast_track_fraction": 0.0,
        "experiment_group": "large_tertiary_ed_300_capacity_benchmark",
        "output_root": "cluster_outputs/large_tertiary_ed_300_capacity_benchmark_raw",
        "major_zone_bed_multiplier": 2.0,
        "minor_zone_capacity_multiplier": 2.0,
        "observation_bed_multiplier": "",
        "downstream_ward_capacity_multiplier": 1.25,
        "icu_acceptance_probability": "",
        "doctor_count_override": "",
        "doctor_count_delta": "",
        "doctor_dispatch_policy": "",
        "benchmark_run_id": run_id,
        "benchmark_basis": "large_tertiary_ed_300_capacity_benchmark",
        "scenario_module": module,
        "standard_equivalent_patients_per_day": int(standard_equivalent),
        "actual_simulated_arrivals": int(actual_arrivals),
        "simulation_scale_factor": round(actual_arrivals / float(standard_equivalent), 6),
        "load_multiplier": "",
        "arrival_profile_mode": "normal",
        "burst_window_min": "",
        "equivalent_arrival_rate_per_hour": "",
        "ctas_mix": _json(BASELINE_CTAS_MIX),
        "resource_scaling_policy": "unscaled_staff_scaled_patients",
        "physicians": 10,
        "triage_nurses": 3,
        "bedside_nurses": 24,
        "observation_beds": 50,
        "high_acuity_beds": 16,
        "rescue_beds": 8,
        "diagnostic_capacity": "",
        "standard_resource_mapping_note": (
            "large_tertiary_ed_300 logical resources mapped onto week13 ED map: "
            "high_acuity->major injuries zone, observation->minor injuries zone, rescue->trauma room when available."
        ),
        "notes": "",
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for run_id, multiplier, actual, standard in [
        ("A_LOAD_0p50_seed42", 0.50, 50, 150),
        ("A_LOAD_0p75_seed42", 0.75, 75, 225),
        ("A_LOAD_1p00_seed42", 1.00, 100, 300),
        ("A_LOAD_1p25_seed42", 1.25, 125, 375),
        ("A_LOAD_1p50_seed42", 1.50, 150, 450),
        ("A_LOAD_1p60_seed42", 1.60, 160, 480),
        ("A_LOAD_1p75_seed42", 1.75, 175, 525),
        ("A_LOAD_2p00_seed42", 2.00, 200, 600),
        ("A_LOAD_2p25_seed42", 2.25, 225, 675),
        ("A_LOAD_2p50_seed42", 2.50, 250, 750),
        ("A_LOAD_3p00_seed42", 3.00, 300, 900),
    ]:
        row = _base_row(run_id, "daily_capacity", actual_arrivals=actual, standard_equivalent=standard)
        row["load_multiplier"] = multiplier
        rows.append(row)

    for window in [240, 180, 120, 90, 60, 45, 30, 20]:
        run_id = f"B_BURST_{window}_seed42"
        row = _base_row(run_id, "burst_influx", actual_arrivals=N_SIM_1X, standard_equivalent=STANDARD_EQ_1X)
        row["arrival_profile_mode"] = "burst"
        row["burst_window_min"] = window
        row["equivalent_arrival_rate_per_hour"] = round(STANDARD_EQ_1X / (window / 60.0), 3)
        row["notes"] = "burst_window_min is benchmark metadata; minute-level burst scheduler still needs runtime validation"
        rows.append(row)

    for run_id, mix in CRITICAL_MIXES.items():
        row = _base_row(run_id, "critical_severity", actual_arrivals=N_SIM_1X, standard_equivalent=STANDARD_EQ_1X)
        row["ctas_mix"] = _json(mix)
        row["notes"] = "ctas_mix is applied during patient symptom sampling when benchmark metadata is present"
        rows.append(row)

    return rows


def write_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in FIELDNAMES})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build large tertiary ED-300 auto capacity benchmark scenarios.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows()
    write_rows(rows, Path(args.output))
    print(json.dumps({"output": str(Path(args.output)), "scenario_count": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
