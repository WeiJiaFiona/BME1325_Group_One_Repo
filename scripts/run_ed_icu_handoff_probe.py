#!/usr/bin/env python
from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis"
for _path in (str(REPO_ROOT), str(ANALYSIS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from scripts.run_week13_capacity_probe import build_settings_overrides, build_target, load_profiles, load_yaml, validate_minutes_per_step
from scripts.run_week13_smoke import run_smoke
from success_metrics import compute_success_metrics


DEFAULT_CONFIG = REPO_ROOT / "configs" / "week13_capacity_experiment.yaml"
DEFAULT_PROFILES = REPO_ROOT / "configs" / "hospital_level_profiles.json"
DEFAULT_JSON = ANALYSIS_DIR / "ed_icu_handoff_probe_report.json"
DEFAULT_MD = ANALYSIS_DIR / "ed_icu_handoff_probe_report.md"
DEFAULT_CSV = ANALYSIS_DIR / "ed_icu_handoff_probe_summary.csv"


def _status_payload(sim_dir: Path) -> dict[str, Any]:
    sim_status = json.loads((sim_dir / "sim_status.json").read_text(encoding="utf-8"))
    data_collection = json.loads((sim_dir / "reverie" / "data_collection.json").read_text(encoding="utf-8"))
    patient_records = dict(data_collection.get("Patient", {}) or {})
    ed_los = []
    for record in patient_records.values():
        start = record.get("ed_arrival_minute")
        end = record.get("ed_exit_minute")
        if start is None or end is None:
            continue
        ed_los.append(int(end) - int(start))
    resources = dict(sim_status.get("resources", {}) or {})
    downstream = dict(sim_status.get("downstream", {}) or {})
    minutes_per_step = int(resources.get("time_scale_minutes_per_step", 1) or 1)
    success_metrics = compute_success_metrics(
        patient_records=patient_records,
        total_arrived_patients=int(resources.get("total_arrived_patients", len(patient_records)) or len(patient_records)),
        failure_rate=resources.get("failure_rate"),
        queue_exposure_record_count=sum(1 for row in patient_records.values() if isinstance(row.get("queue_exposure"), dict)),
        physical_window_minutes=int(sim_status.get("step", 0) or 0) * minutes_per_step,
        ctas_targets=None,
    )
    return {
        "sim_dir": str(sim_dir),
        "transfer_request_count": int(downstream.get("transfer_request_count", resources.get("downstream_transfer_request_count", 0)) or 0),
        "accepted_transfer_count": int(downstream.get("accepted_transfer_count", resources.get("downstream_accepted_transfer_count", 0)) or 0),
        "pending_transfer_count": int(downstream.get("pending_transfer_count", resources.get("downstream_pending_transfer_count", 0)) or 0),
        "boarding_patient_count": int(downstream.get("boarding_patient_count", resources.get("downstream_boarding_patient_count", 0)) or 0),
        "boarding_timeout_count": int(resources.get("boarding_timeout_count", 0) or 0),
        "failure_rate": float(resources.get("failure_rate", 0.0) or 0.0),
        "failure_reason_counts": dict(resources.get("failure_reason_counts", {}) or {}),
        "throughput_success_rate": success_metrics.get("throughput_success_rate"),
        "operational_success_rate": success_metrics.get("operational_success_rate"),
        "mean_ed_los": (sum(ed_los) / len(ed_los)) if ed_los else None,
        "max_ed_los": max(ed_los) if ed_los else None,
        "icu_capacity": int(downstream.get("icu_capacity", resources.get("downstream_icu_capacity", 0)) or 0),
        "ward_capacity": int(downstream.get("ward_capacity", resources.get("downstream_ward_capacity", 0)) or 0),
    }


def main() -> None:
    config = load_yaml(DEFAULT_CONFIG)
    profiles = load_profiles(DEFAULT_PROFILES)
    profile_name = "small_county_ed"
    load_factor = 2.0
    run_steps = 200
    seed = 42
    minutes_per_step = validate_minutes_per_step(config, 1)
    profile = profiles[profile_name]
    rows: list[dict[str, Any]] = []
    for icu_capacity in (0, 1, 6):
        target = build_target(profile_name, load_factor, seed, run_steps, minutes_per_step) + f"_icu{icu_capacity}"
        smoke_summary = run_smoke(
            port=8016,
            origin="ed_sim_n5",
            target=target,
            run_steps=run_steps,
            max_attempts=3,
            settings_overrides={
                **build_settings_overrides(
                    profile_name=profile_name,
                    profile=profile,
                    load_factor=load_factor,
                    seed=seed,
                    minutes_per_step=minutes_per_step,
                    config=config,
                ),
                "simulate_hospital_admission": True,
                "icu_capacity": int(icu_capacity),
                "hospital_profile_name": profile_name,
            },
        )
        sim_dir = Path(smoke_summary["sim_dir"])
        row = {
            "hospital_profile": profile_name,
            "load_factor": load_factor,
            "seed": seed,
            "run_steps": run_steps,
            **_status_payload(sim_dir),
        }
        rows.append(row)
    envelope = {
        "hospital_profile": profile_name,
        "load_factor": load_factor,
        "seed": seed,
        "run_steps": run_steps,
        "results": rows,
    }
    DEFAULT_JSON.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(DEFAULT_CSV, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "icu_capacity",
                "ward_capacity",
                "transfer_request_count",
                "accepted_transfer_count",
                "pending_transfer_count",
                "boarding_patient_count",
                "boarding_timeout_count",
                "failure_rate",
                "throughput_success_rate",
                "operational_success_rate",
                "mean_ed_los",
                "max_ed_los",
                "sim_dir",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})
    lines = [
        "# ED–ICU Handoff Probe",
        "",
        "| icu_capacity | ward_capacity | transfer_request_count | accepted_transfer_count | pending_transfer_count | boarding_patient_count | boarding_timeout_count | failure_rate | throughput_success_rate | operational_success_rate | mean_ed_los | max_ed_los |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['icu_capacity']} | {row['ward_capacity']} | {row['transfer_request_count']} | {row['accepted_transfer_count']} | "
            f"{row['pending_transfer_count']} | {row['boarding_patient_count']} | {row['boarding_timeout_count']} | "
            f"{row['failure_rate']} | {row['throughput_success_rate']} | {row['operational_success_rate']} | {row['mean_ed_los']} | {row['max_ed_los']} |"
        )
    DEFAULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(envelope, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
