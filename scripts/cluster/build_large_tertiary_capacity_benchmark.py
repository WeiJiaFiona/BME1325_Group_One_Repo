#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = REPO_ROOT / "configs" / "benchmark" / "large_tertiary_ed_profile.json"
DEFAULT_OUTPUT = REPO_ROOT / "configs" / "benchmark" / "large_tertiary_ed_25run_matrix.csv"
RAW_OUTPUT_ROOT = "cluster_outputs/large_tertiary_ed_300_capacity_benchmark_raw"

BASELINE_PROFILE_NORMAL_PATIENTS = 64
N_SIM_1X = 100
STANDARD_EQ_1X = 300

CRITICAL_MIXES = {
    "C_CRIT_45_seed42": {"L1": 0.05, "L2": 0.40, "L3": 0.42, "L4": 0.11, "L5": 0.02},
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
    "daily_ed_arrivals",
    "arrival_peak_factor",
    "physicians",
    "triage_nurses",
    "bedside_nurses",
    "night_doctor_count",
    "night_nurse_count",
    "resus_bed_count",
    "major_zone_bed_count",
    "minor_zone_capacity",
    "observation_bed_count",
    "infusion_chair_count",
    "eicu_bed_count",
    "lab_capacity",
    "imaging_capacity",
    "ct_capacity",
    "ultrasound_capacity",
    "ward_transfer_capacity_per_day",
    "icu_transfer_capacity_per_day",
    "or_transfer_capacity_per_day",
    "cath_lab_transfer_capacity_per_day",
    "bed_cleaning_turnover_minutes",
    "zone_release_delay_minutes",
    "observation_los_mean_minutes",
    "boarding_timeout_minutes",
    "downstream_transfer_delay_minutes",
    "runtime_effect_notes",
    "notes",
]


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _scale_factor(actual: int, standard: int) -> float:
    return actual / float(standard) if standard else 0.0


def _base_row(profile: dict[str, Any], run_id: str, module: str, *, actual: int, standard: int) -> dict[str, Any]:
    resources = profile["resources"]
    load_factor = actual / float(BASELINE_PROFILE_NORMAL_PATIENTS)
    return {
        "scenario_id": run_id,
        "hospital_profile": "large_tertiary_ed",
        "load_factor": f"{load_factor:.8f}",
        "run_steps": profile.get("run_steps", 1440),
        "seed": profile.get("seed", 42),
        "doctor_count": resources["doctor_count"],
        "nurse_count_total": resources["triage_nurse_count"] + resources["bedside_nurse_count"],
        "triage_nurse_count": resources["triage_nurse_count"],
        "bedside_nurse_count": resources["bedside_nurse_count"],
        "bedside_nurse_service_time_multiplier": 1.0,
        "low_ctas_fast_track_enabled": "False",
        "low_ctas_fast_track_fraction": 0.0,
        "experiment_group": "large_tertiary_ed_300_capacity_benchmark",
        "output_root": RAW_OUTPUT_ROOT,
        "major_zone_bed_multiplier": "",
        "minor_zone_capacity_multiplier": "",
        "observation_bed_multiplier": "",
        "downstream_ward_capacity_multiplier": "",
        "icu_acceptance_probability": "",
        "doctor_count_override": "",
        "doctor_count_delta": "",
        "doctor_dispatch_policy": "",
        "benchmark_run_id": run_id,
        "benchmark_basis": profile["benchmark_basis"],
        "scenario_module": module,
        "standard_equivalent_patients_per_day": standard,
        "actual_simulated_arrivals": actual,
        "simulation_scale_factor": f"{_scale_factor(actual, standard):.6f}",
        "load_multiplier": "",
        "arrival_profile_mode": "normal",
        "burst_window_min": "",
        "equivalent_arrival_rate_per_hour": "",
        "ctas_mix": _json(profile["ctas_mix"]),
        "resource_scaling_policy": profile["simulation_scaling"]["resource_scaling_policy"],
        "daily_ed_arrivals": profile["daily_ed_arrivals"],
        "arrival_peak_factor": profile["arrival_peak_factor"],
        "physicians": resources["doctor_count"],
        "triage_nurses": resources["triage_nurse_count"],
        "bedside_nurses": resources["bedside_nurse_count"],
        "night_doctor_count": resources["night_doctor_count"],
        "night_nurse_count": resources["night_nurse_count"],
        "resus_bed_count": resources["resus_bed_count"],
        "major_zone_bed_count": resources["major_zone_bed_count"],
        "minor_zone_capacity": resources["minor_zone_capacity"],
        "observation_bed_count": resources["observation_bed_count"],
        "infusion_chair_count": resources["infusion_chair_count"],
        "eicu_bed_count": resources["eicu_bed_count"],
        "lab_capacity": resources["lab_capacity"],
        "imaging_capacity": resources["imaging_capacity"],
        "ct_capacity": resources["ct_capacity"],
        "ultrasound_capacity": resources["ultrasound_capacity"],
        "ward_transfer_capacity_per_day": resources["ward_transfer_capacity_per_day"],
        "icu_transfer_capacity_per_day": resources["icu_transfer_capacity_per_day"],
        "or_transfer_capacity_per_day": resources["or_transfer_capacity_per_day"],
        "cath_lab_transfer_capacity_per_day": resources["cath_lab_transfer_capacity_per_day"],
        "bed_cleaning_turnover_minutes": resources["bed_cleaning_turnover_minutes"],
        "zone_release_delay_minutes": resources["zone_release_delay_minutes"],
        "observation_los_mean_minutes": resources["observation_los_mean_minutes"],
        "boarding_timeout_minutes": resources["boarding_timeout_minutes"],
        "downstream_transfer_delay_minutes": resources["downstream_transfer_delay_minutes"],
        "runtime_effect_notes": "major/minor/resus/observation tertiary resources are preserved as benchmark fields; unsupported map concepts must be treated as metadata_only.",
        "notes": profile.get("source_context", ""),
    }


def build_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_id, multiplier in [
        ("A_LOAD_0p50_seed42", 0.50),
        ("A_LOAD_0p75_seed42", 0.75),
        ("A_LOAD_1p00_seed42", 1.00),
        ("A_LOAD_1p25_seed42", 1.25),
        ("A_LOAD_1p50_seed42", 1.50),
        ("A_LOAD_1p60_seed42", 1.60),
        ("A_LOAD_1p75_seed42", 1.75),
        ("A_LOAD_2p00_seed42", 2.00),
        ("A_LOAD_2p25_seed42", 2.25),
        ("A_LOAD_2p50_seed42", 2.50),
        ("A_LOAD_3p00_seed42", 3.00),
    ]:
        row = _base_row(
            profile,
            run_id,
            "daily_capacity",
            actual=max(1, round(N_SIM_1X * multiplier)),
            standard=round(STANDARD_EQ_1X * multiplier),
        )
        row["load_multiplier"] = multiplier
        rows.append(row)

    for window in [240, 180, 120, 90, 60, 45, 30, 20]:
        run_id = f"B_BURST_{window}_seed42"
        row = _base_row(profile, run_id, "burst_influx", actual=N_SIM_1X, standard=STANDARD_EQ_1X)
        row["arrival_profile_mode"] = "burst"
        row["burst_window_min"] = window
        row["equivalent_arrival_rate_per_hour"] = round(STANDARD_EQ_1X / (window / 60.0), 3)
        row["notes"] = "burst_window_min is benchmark metadata; current runtime burst support is hour-level unless minute scheduler is added."
        rows.append(row)

    for run_id, mix in CRITICAL_MIXES.items():
        row = _base_row(profile, run_id, "critical_severity", actual=N_SIM_1X, standard=STANDARD_EQ_1X)
        row["ctas_mix"] = _json(mix)
        row["notes"] = "ctas_mix is applied during benchmark patient symptom sampling; validate actual CTAS distribution after run."
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
    parser = argparse.ArgumentParser(description="Build large tertiary ED capacity benchmark matrix.")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    rows = build_rows(profile)
    write_rows(rows, Path(args.output))
    print(json.dumps({"output": str(Path(args.output)), "scenario_count": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
