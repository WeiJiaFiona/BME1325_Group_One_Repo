#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "analysis",
    REPO_ROOT / "scripts",
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from analysis.build_metric_calibration_report import build_metric_calibration_report
from analysis.build_runtime_evidence_report import build_runtime_evidence_report
from analysis.build_success_failure_report import validate_success_failure_report
from scripts.cluster.run_one_taskB_scenario_headless import (
    BACKEND_DIR,
    RUNTIME_LOG_DIR,
    STORAGE_ROOT,
    _artifact_snapshot,
    _data_collection_path,
    _finish_backend_process,
    _prepare_backend_only_origin,
    _read_text_tail,
    _status_payload,
    _wait_for_backend_artifacts,
    _write_backend_command,
    write_status,
)
from scripts.run_week13_capacity_probe import build_settings_overrides, load_profiles, load_yaml, validate_minutes_per_step


DEFAULT_SCENARIO_CSV = REPO_ROOT / "configs" / "cluster" / "ed_bottleneck_v1_scenarios.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "ed_bottleneck_v1"
CONFIG_PATH = REPO_ROOT / "configs" / "week13_capacity_experiment.yaml"
PROFILES_PATH = REPO_ROOT / "configs" / "hospital_level_profiles.json"


def _parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_scenarios(csv_path: str | Path) -> list[dict[str, Any]]:
    with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_scenario_row(csv_path: str | Path, row_index: int) -> dict[str, Any]:
    rows = load_scenarios(csv_path)
    if int(row_index) < 1 or int(row_index) > len(rows):
        raise IndexError(f"row-index {row_index} out of range 1..{len(rows)}")
    row = dict(rows[int(row_index) - 1])
    for key in (
        "run_steps",
        "seed",
        "doctor_count",
        "nurse_count_total",
        "triage_nurse_count",
        "bedside_nurse_count",
    ):
        row[key] = int(row[key])
    for key in ("load_factor", "bedside_nurse_service_time_multiplier", "low_ctas_fast_track_fraction"):
        row[key] = float(row[key])
    row["low_ctas_fast_track_enabled"] = _parse_bool(row["low_ctas_fast_track_enabled"])
    return row


def scenario_output_dir(output_root: str | Path, row: dict[str, Any]) -> Path:
    return Path(output_root) / str(row["experiment_group"]) / str(row["scenario_id"])


def _result_row_from_report(
    *,
    row: dict[str, Any],
    report: dict[str, Any],
    sim_dir: Path,
    target_sim: str,
) -> dict[str, Any]:
    return {
        "scenario_id": row["scenario_id"],
        "experiment_group": row["experiment_group"],
        "hospital_profile": row["hospital_profile"],
        "load_factor": float(row["load_factor"]),
        "run_steps": int(row["run_steps"]),
        "seed": int(row["seed"]),
        "doctor_count": int(row["doctor_count"]),
        "nurse_count_total": int(row["nurse_count_total"]),
        "triage_nurse_count": int(row["triage_nurse_count"]),
        "bedside_nurse_count": int(row["bedside_nurse_count"]),
        "bedside_nurse_service_time_multiplier": float(row["bedside_nurse_service_time_multiplier"]),
        "low_ctas_fast_track_enabled": bool(row["low_ctas_fast_track_enabled"]),
        "low_ctas_fast_track_fraction": float(row["low_ctas_fast_track_fraction"]),
        "total_arrived_patients": report.get("total_arrived_patients"),
        "failure_rate": report.get("failure_rate"),
        "queue_success_rate": report.get("queue_success_rate"),
        "ctas_success_rate": report.get("ctas_success_rate"),
        "throughput_success_rate": report.get("throughput_success_rate"),
        "operational_success_rate": report.get("operational_success_rate"),
        "queue_exposed_patients": report.get("queue_exposed_patients"),
        "bedside_nurse_queue_exposed_patients": report.get("bedside_nurse_queue_exposed_patients"),
        "completed_care_count": report.get("completed_care_count"),
        "still_in_ed_count": report.get("still_in_ed_count"),
        "median_bedside_nurse_exposure_minutes": report.get("median_bedside_nurse_exposure_minutes"),
        "p90_bedside_nurse_exposure_minutes": report.get("p90_bedside_nurse_exposure_minutes"),
        "max_bedside_nurse_exposure_minutes": report.get("max_bedside_nurse_exposure_minutes"),
        "bedside_nurse_utilization_status": report.get("bedside_nurse_utilization_status"),
        "reinsert_patient_count": report.get("reinsert_patient_count"),
        "max_reinsert_count": report.get("max_reinsert_count"),
        "top_reinsert_patients": report.get("top_reinsert_patients"),
        "nurse_assignment_repetition_ratio": report.get("nurse_assignment_repetition_ratio"),
        "patients_never_served_but_exposed_count": report.get("patients_never_served_but_exposed_count"),
        "sim_dir": str(sim_dir),
        "target_sim": target_sim,
    }


def _scenario_info(row: dict[str, Any], output_dir: Path, target_sim: str) -> dict[str, Any]:
    return {
        **row,
        "target_sim": target_sim,
        "output_dir": str(output_dir),
        "low_ctas_fast_track_ctas_levels": [4, 5],
    }


def _implementation_blocked_payload(
    *,
    row: dict[str, Any],
    output_dir: Path,
    row_index: int,
    reason: str,
) -> dict[str, Any]:
    target_sim = f"ed_bottleneck_v1_{row['scenario_id']}"
    payload = {
        "scenario_id": row["scenario_id"],
        "row_index": row_index,
        "status": "implementation_blocked",
        "stage": "implementation_blocked",
        "scenario": _scenario_info(row, output_dir, target_sim),
        "sim_dir": None,
        "result_row": None,
        "error": reason,
        "traceback": None,
    }
    write_status(output_dir, payload)
    return payload


def run_one(
    *,
    row: dict[str, Any],
    output_root: str | Path,
    row_index: int,
    backend_only: bool,
    dry_run: bool = False,
) -> dict[str, Any]:
    output_dir = scenario_output_dir(output_root, row)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_sim = f"ed_bottleneck_v1_{row['scenario_id']}"
    sim_dir = (STORAGE_ROOT / target_sim).resolve()
    scenario = _scenario_info(row, output_dir, target_sim)

    if dry_run:
        payload = {
            "scenario_id": row["scenario_id"],
            "row_index": row_index,
            "status": "dry_run",
            "stage": "dry_run",
            "scenario": scenario,
            "sim_dir": str(sim_dir),
            "result_row": None,
            "error": None,
            "traceback": None,
        }
        write_status(output_dir, payload)
        return payload

    if not backend_only:
        return _implementation_blocked_payload(
            row=row,
            output_dir=output_dir,
            row_index=row_index,
            reason="Only --backend-only mode is implemented for ED bottleneck V1.",
        )

    if float(row["bedside_nurse_service_time_multiplier"]) != 1.0:
        return _implementation_blocked_payload(
            row=row,
            output_dir=output_dir,
            row_index=row_index,
            reason=(
                "bedside_nurse_service_time_multiplier requires a confirmed bedside "
                "service-duration hook; V1 records the config but does not alter clinical workflow."
            ),
        )

    config = load_yaml(CONFIG_PATH)
    profiles = load_profiles(PROFILES_PATH)
    profile = dict(profiles[row["hospital_profile"]])
    profile["doctor_count"] = int(row["doctor_count"])
    profile["nurse_count"] = int(row["bedside_nurse_count"])
    minutes_per_step = validate_minutes_per_step(config, 1)
    preload_patient_count = round(int(profile["normal_patient_count"]) * float(row["load_factor"]))
    settings_overrides = {
        **build_settings_overrides(
            profile_name=row["hospital_profile"],
            profile=profile,
            load_factor=float(row["load_factor"]),
            seed=int(row["seed"]),
            minutes_per_step=minutes_per_step,
            config=config,
        ),
        "doctor_starting_amount": int(row["doctor_count"]),
        "triage_starting_amount": int(row["triage_nurse_count"]),
        "bedside_starting_amount": int(row["bedside_nurse_count"]),
        "nurse_count_total": int(row["nurse_count_total"]),
        "bedside_nurse_service_time_multiplier": float(row["bedside_nurse_service_time_multiplier"]),
        "low_ctas_fast_track_enabled": bool(row["low_ctas_fast_track_enabled"]),
        "low_ctas_fast_track_fraction": float(row["low_ctas_fast_track_fraction"]),
        "low_ctas_fast_track_ctas_levels": [4, 5],
        "background_arrival_enabled": False,
        "patient_rate_modifier": 0,
    }

    backend_log = RUNTIME_LOG_DIR / f"ed_bottleneck_v1_{row['scenario_id']}.log"
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    if sim_dir.exists():
        import shutil

        shutil.rmtree(sim_dir)

    stage = "backend_only_prepare"
    proc: subprocess.Popen | None = None
    log_handle = None
    finished_backend = False
    try:
        seed_origin = _prepare_backend_only_origin(row=row, settings_overrides=settings_overrides)
        env = os.environ.copy()
        env.setdefault("EDSIM_MODE", "auto")
        env.setdefault("LLM_MODE", "local_only")
        env.setdefault("EMBEDDING_MODE", "local_only")
        env.setdefault("ENABLE_LLM_AGENTS", "0")
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env["REVERIE_FRONTEND_CONTROL"] = "1"
        stage = "backend_only_start"
        log_handle = backend_log.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            [
                sys.executable,
                "reverie.py",
                "--origin",
                seed_origin,
                "--target",
                target_sim,
                "--frontend_ui",
                "yes",
                "--headless",
                "yes",
                "--write_movement",
                "yes",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
        )
        stage = "backend_only_command"
        time.sleep(3)
        if proc.poll() is not None:
            raise RuntimeError(f"backend process exited early with code {proc.returncode}")
        _write_backend_command(target_sim, f"run {int(row['run_steps'])}")
        stage = "backend_only_wait_artifacts"
        snapshot = _wait_for_backend_artifacts(sim_dir, int(row["run_steps"]), max(300, min(21600, int(row["run_steps"]) * 15)))
        if not snapshot["artifact_complete"]:
            raise RuntimeError("backend artifacts incomplete")
        stage = "backend_only_save_finish"
        _finish_backend_process(target_sim, proc)
        finished_backend = True
        if log_handle is not None:
            log_handle.close()
            log_handle = None

        stage = "backend_only_reports"
        probe_report = build_runtime_evidence_report(
            sim_dir=sim_dir,
            output_path=output_dir / "runtime_evidence_probe_report.json",
            hospital_profile=row["hospital_profile"],
            load_factor=float(row["load_factor"]),
            preload_patient_count=preload_patient_count,
            run_steps_requested=int(row["run_steps"]),
        )
        probe_path = output_dir / "probe_envelope.json"
        probe_path.write_text(
            json.dumps(
                {
                    "hospital_profile": row["hospital_profile"],
                    "load_factor": float(row["load_factor"]),
                    "preload_patient_count": preload_patient_count,
                    "run_steps_requested": int(row["run_steps"]),
                    "run_steps_completed": probe_report["run_steps_completed"],
                    "time_scale_minutes_per_step": minutes_per_step,
                    "physical_window_minutes": probe_report["physical_window_minutes"],
                    "target_sim": target_sim,
                    "sim_dir": str(sim_dir),
                    "runtime_evidence_completeness": probe_report,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        calibration = build_metric_calibration_report(
            sim_dir=sim_dir,
            probe_report_path=probe_path,
            composition_output_path=output_dir / "failure_composition_report.json",
            sensitivity_output_path=output_dir / "metric_sensitivity_report.json",
            calibrated_output_path=output_dir / "success_failure_report.json",
            summary_output_path=output_dir / "metric_calibration_summary.md",
        )
        report = calibration["success_failure_report_calibrated"]
        snapshot = _artifact_snapshot(sim_dir, int(row["run_steps"]), output_dir / "success_failure_report.json")
        validate_success_failure_report(report, patient_record_count=snapshot.get("data_collection_patient_count"))
        payload = _status_payload(
            row={**row, "nurse_count": row["nurse_count_total"], "time_scale_minutes_per_step": 1},
            row_index=row_index,
            status="success",
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=sim_dir,
            resolved_sim_dir=sim_dir,
            stage="backend_only_completed",
            scenario=scenario,
            extra={
                **snapshot,
                "sim_dir": str(sim_dir),
                "success_failure_report_valid": True,
                "success_failure_report_rebuilt_from": str(_data_collection_path(sim_dir)),
                "report_generation_source": "post_backend_rebuild",
                "backend_stdout_tail": _read_text_tail(backend_log),
                "backend_log_path": str(backend_log),
                "result_row": _result_row_from_report(row=row, report=report, sim_dir=sim_dir, target_sim=target_sim),
            },
        )
        write_status(output_dir, payload)
        return payload
    except Exception as exc:
        snapshot = _artifact_snapshot(sim_dir, int(row["run_steps"]), output_dir / "success_failure_report.json")
        payload = _status_payload(
            row={**row, "nurse_count": row["nurse_count_total"], "time_scale_minutes_per_step": 1},
            row_index=row_index,
            status="partial_failed" if snapshot["sim_status_exists"] or snapshot["movement_count"] else "failed",
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=sim_dir,
            resolved_sim_dir=sim_dir if sim_dir.exists() else None,
            error=str(exc),
            traceback_text=traceback.format_exc(),
            stage=stage,
            scenario=scenario,
            extra={**snapshot, "backend_stdout_tail": _read_text_tail(backend_log), "backend_log_path": str(backend_log)},
        )
        write_status(output_dir, payload)
        return payload
    finally:
        if not finished_backend and proc is not None and proc.poll() is None:
            try:
                _finish_backend_process(target_sim, proc, timeout_seconds=20)
            except Exception:
                proc.terminate()
        if log_handle is not None:
            log_handle.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one ED bottleneck V1 scenario.")
    parser.add_argument("--scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--row-index", type=int, required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    row = read_scenario_row(args.scenario_csv, args.row_index)
    result = run_one(
        row=row,
        output_root=args.output_root,
        row_index=args.row_index,
        backend_only=bool(args.backend_only),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
