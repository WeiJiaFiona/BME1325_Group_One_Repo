#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
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
from scripts.run_week13_capacity_probe import build_settings_overrides, load_profiles, load_yaml, validate_minutes_per_step
from scripts.run_week13_smoke import run_smoke


DEFAULT_SCENARIO_CSV = REPO_ROOT / "configs" / "cluster" / "taskB_missing_scenarios.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "taskB_missing"
CONFIG_PATH = REPO_ROOT / "configs" / "week13_capacity_experiment.yaml"
PROFILES_PATH = REPO_ROOT / "configs" / "hospital_level_profiles.json"
STORAGE_ROOT = REPO_ROOT / "environment" / "frontend_server" / "storage"
TEMP_ROOT = REPO_ROOT / "environment" / "frontend_server" / "temp_storage"
BACKEND_DIR = REPO_ROOT / "reverie" / "backend_server"
RUNTIME_LOG_DIR = REPO_ROOT / "runtime_data" / "logs"


def _read_text_tail(path: str | Path, max_chars: int = 12000) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-max_chars:]


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _data_collection_path(sim_dir: Path) -> Path:
    nested_path = sim_dir / "reverie" / "data_collection.json"
    if nested_path.exists():
        return nested_path
    return sim_dir / "data_collection.json"


def _patient_record_count(data_collection: Any) -> int:
    if isinstance(data_collection, list):
        return sum(1 for row in data_collection if isinstance(row, dict))
    if not isinstance(data_collection, dict):
        return 0
    patients = data_collection.get("Patient", data_collection)
    if isinstance(patients, dict):
        return sum(1 for row in patients.values() if isinstance(row, dict))
    if isinstance(patients, list):
        return sum(1 for row in patients if isinstance(row, dict))
    return 0


def _data_collection_patient_count(sim_dir: Path) -> int:
    data_collection_path = _data_collection_path(sim_dir)
    if not data_collection_path.exists():
        return 0
    try:
        return _patient_record_count(_load_json(data_collection_path))
    except Exception:
        return 0


def load_scenarios(csv_path: str | Path) -> list[dict[str, Any]]:
    csv_path = Path(csv_path)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_scenario_row(csv_path: str | Path, row_index: int) -> dict[str, Any]:
    rows = load_scenarios(csv_path)
    if int(row_index) < 1 or int(row_index) > len(rows):
        raise IndexError(f"row-index {row_index} out of range 1..{len(rows)}")
    row = dict(rows[int(row_index) - 1])
    row["load_factor"] = float(row["load_factor"])
    row["seed"] = int(row["seed"])
    row["doctor_count"] = int(row["doctor_count"])
    row["nurse_count"] = int(row["nurse_count"])
    row["run_steps"] = int(row["run_steps"])
    row["time_scale_minutes_per_step"] = int(row["time_scale_minutes_per_step"])
    return row


def scenario_output_dir(output_root: str | Path, scenario_id: str) -> Path:
    return Path(output_root) / str(scenario_id)


def write_status(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scenario_status.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _result_row_from_report(
    *,
    row: dict[str, Any],
    profile: dict[str, Any],
    preload_patient_count: int,
    report: dict[str, Any],
    failure_composition_report: dict[str, Any] | None,
    sim_dir: Path,
    target_sim: str,
    artifact_status: str,
) -> dict[str, Any]:
    evidence = report.get("evidence_completeness", {}) if isinstance(report.get("evidence_completeness"), dict) else {}
    return {
        "hospital_profile": row["hospital_profile"],
        "staffing_profile": row["staffing_profile"],
        "load_factor": float(row["load_factor"]),
        "seed": int(row["seed"]),
        "doctor_count": int(row["doctor_count"]),
        "nurse_count": int(row["nurse_count"]),
        "normal_patient_count": int(profile["normal_patient_count"]),
        "preload_patient_count": preload_patient_count,
        "total_arrived_patients": report["total_arrived_patients"],
        "failure_rate": report["failure_rate"],
        "failure_reason_counts": (failure_composition_report or {}).get("failure_reason_counts", {}),
        "queue_success_rate": report["queue_success_rate"],
        "ctas_success_rate": report["ctas_success_rate"],
        "throughput_success_rate": report["throughput_success_rate"],
        "operational_success_rate": report["operational_success_rate"],
        "max_doctor_queue": evidence.get("max_doctor_queue"),
        "queue_exposed_patients": report.get("queue_exposed_patients"),
        "first_doctor_contact_at_count": evidence.get("first_doctor_contact_at_count"),
        "ed_exit_at_count": evidence.get("ed_exit_at_count"),
        "runtime_evidence_completeness": evidence,
        "throughput_window_warning": report.get("throughput_window_warning"),
        "sim_dir": str(sim_dir),
        "target_sim": target_sim,
        "artifact_status": artifact_status,
    }


def _artifact_snapshot(sim_dir: Path, run_steps: int, success_report_path: Path | None = None) -> dict[str, Any]:
    sim_status_path = sim_dir / "sim_status.json"
    movement_dir = sim_dir / "movement"
    data_collection_path = _data_collection_path(sim_dir)
    status_payload: dict[str, Any] = {}
    if sim_status_path.exists():
        try:
            status_payload = _load_json(sim_status_path)
        except Exception:
            status_payload = {}
    movement_count = len(list(movement_dir.glob("*.json"))) if movement_dir.exists() else 0
    step_completed = status_payload.get("step") if isinstance(status_payload, dict) else None
    data_collection_patient_count = _data_collection_patient_count(sim_dir)
    success_failure_report_exists = bool(success_report_path and success_report_path.exists())
    return {
        "run_steps": int(run_steps),
        "step_completed": step_completed,
        "movement_count": movement_count,
        "data_collection_exists": data_collection_path.exists(),
        "data_collection_patient_count": data_collection_patient_count,
        "sim_status_exists": sim_status_path.exists(),
        "success_failure_report_exists": success_failure_report_exists,
        "artifact_complete": (
            sim_status_path.exists()
            and isinstance(step_completed, int)
            and step_completed >= int(run_steps) - 1
            and movement_count >= int(run_steps)
            and data_collection_path.exists()
            and data_collection_patient_count > 0
        ),
    }


def _safe_result_keys(result: Any) -> list[str]:
    return sorted(result.keys()) if isinstance(result, dict) else []


def _target_sim_from_result(result: Any, fallback: str) -> str:
    if isinstance(result, dict):
        raw = result.get("target") or result.get("target_sim")
        if raw:
            return str(raw)
    return fallback


def _resolve_sim_dir_from_result(result: Any, target_sim: str) -> Path:
    if isinstance(result, dict):
        raw = result.get("sim_dir") or result.get("target_sim_dir") or result.get("artifact_dir")
        if raw:
            return Path(raw).resolve()
    return (STORAGE_ROOT / target_sim).resolve()


def _prepare_backend_only_origin(*, row: dict[str, Any], settings_overrides: dict[str, Any]) -> str:
    origin = str(row.get("origin") or "ed_sim_n5")
    source_dir = STORAGE_ROOT / origin
    seed_origin = f"_cluster_seed_{row['scenario_id']}"
    seed_dir = STORAGE_ROOT / seed_origin
    if seed_dir.exists():
        shutil.rmtree(seed_dir)
    shutil.copytree(source_dir, seed_dir)
    meta_path = seed_dir / "reverie" / "meta.json"
    meta = _load_json(meta_path)
    meta.update(settings_overrides)
    meta["fork_sim_code"] = origin
    meta["step"] = 0
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return seed_origin


def _write_backend_command(target_sim: str, command: str) -> Path:
    command_dir = TEMP_ROOT / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    command_path = command_dir / f"cmd_{int(time.time() * 1000)}_{target_sim}.json"
    command_path.write_text(
        json.dumps({"id": command_path.stem, "command": command}, ensure_ascii=False),
        encoding="utf-8",
    )
    return command_path


def _finish_backend_process(target_sim: str, proc: subprocess.Popen | None, timeout_seconds: int = 60) -> None:
    if proc is None or proc.poll() is not None:
        return
    _write_backend_command(target_sim, "save and finish")
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def _wait_for_backend_artifacts(sim_dir: Path, run_steps: int, timeout_seconds: int) -> dict[str, Any]:
    start = time.time()
    latest = _artifact_snapshot(sim_dir, run_steps)
    while time.time() - start < timeout_seconds:
        latest = _artifact_snapshot(sim_dir, run_steps)
        if latest["artifact_complete"]:
            return latest
        time.sleep(1)
    return latest


def _run_backend_only(
    *,
    row: dict[str, Any],
    scenario_info: dict[str, Any],
    output_dir: Path,
    expected_sim_dir: Path,
    row_index: int | None,
    debug: bool,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_yaml(CONFIG_PATH)
    profiles = load_profiles(PROFILES_PATH)
    minutes_per_step = validate_minutes_per_step(config, int(row["time_scale_minutes_per_step"]))
    profile = dict(profiles[row["hospital_profile"]])
    profile["doctor_count"] = int(row["doctor_count"])
    profile["nurse_count"] = int(row["nurse_count"])
    settings_overrides = {
        **build_settings_overrides(
            profile_name=row["hospital_profile"],
            profile=profile,
            load_factor=float(row["load_factor"]),
            seed=int(row["seed"]),
            minutes_per_step=minutes_per_step,
            config=config,
        ),
        "background_arrival_enabled": False,
        "patient_rate_modifier": 0,
    }
    target_sim = f"cluster_taskB_{row['scenario_id']}"
    sim_dir = (STORAGE_ROOT / target_sim).resolve()
    backend_log = RUNTIME_LOG_DIR / f"taskB_backend_only_{row['scenario_id']}.log"
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    if sim_dir.exists():
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
        timeout_seconds = max(300, min(21600, int(row["run_steps"]) * 15))
        snapshot = _wait_for_backend_artifacts(sim_dir, int(row["run_steps"]), timeout_seconds)
        if not snapshot["artifact_complete"]:
            payload = _status_payload(
                row=row,
                row_index=row_index,
                status="partial" if snapshot["sim_status_exists"] or snapshot["movement_count"] else "failed",
                target_sim=target_sim,
                output_dir=output_dir,
                expected_sim_dir=expected_sim_dir,
                resolved_sim_dir=sim_dir,
                error="backend artifacts incomplete",
                traceback_text=None,
                stage=stage,
                scenario=scenario_info,
                extra={
                    **snapshot,
                    "backend_stdout_tail": _read_text_tail(backend_log),
                    "backend_stderr_tail": "",
                    "backend_log_path": str(backend_log),
                },
            )
            write_status(output_dir, payload)
            return payload

        stage = "backend_only_save_finish"
        _finish_backend_process(target_sim, proc)
        finished_backend = True
        if log_handle is not None:
            log_handle.close()
            log_handle = None
        snapshot = _artifact_snapshot(sim_dir, int(row["run_steps"]), output_dir / "success_failure_report.json")
        if not snapshot["artifact_complete"]:
            raise RuntimeError("backend artifacts incomplete after save and finish")

        stage = "backend_only_reports"
        preload_patient_count = round(int(profile["normal_patient_count"]) * float(row["load_factor"]))
        probe_report = build_runtime_evidence_report(
            sim_dir=sim_dir,
            output_path=output_dir / "runtime_evidence_probe_report.json",
            hospital_profile=row["hospital_profile"],
            load_factor=float(row["load_factor"]),
            preload_patient_count=preload_patient_count,
            run_steps_requested=int(row["run_steps"]),
        )
        probe_envelope_path = output_dir / "probe_envelope.json"
        probe_envelope = {
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
        }
        probe_envelope_path.write_text(json.dumps(probe_envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        calibration = build_metric_calibration_report(
            sim_dir=sim_dir,
            probe_report_path=probe_envelope_path,
            composition_output_path=output_dir / "failure_composition_report.json",
            sensitivity_output_path=output_dir / "metric_sensitivity_report.json",
            calibrated_output_path=output_dir / "success_failure_report.json",
            summary_output_path=output_dir / "metric_calibration_summary.md",
        )
        stage = "backend_only_validate_report"
        snapshot = _artifact_snapshot(sim_dir, int(row["run_steps"]), output_dir / "success_failure_report.json")
        calibrated = calibration["success_failure_report_calibrated"]
        validate_success_failure_report(calibrated, patient_record_count=snapshot.get("data_collection_patient_count"))
        result_row = _result_row_from_report(
            row=row,
            profile=profile,
            preload_patient_count=preload_patient_count,
            report=calibrated,
            failure_composition_report=calibration.get("failure_composition_report"),
            sim_dir=sim_dir,
            target_sim=target_sim,
            artifact_status="backend_only",
        )
        payload = _status_payload(
            row=row,
            row_index=row_index,
            status="success",
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=expected_sim_dir,
            resolved_sim_dir=sim_dir,
            stage="backend_only_completed",
            scenario=scenario_info,
            extra={
                **snapshot,
                "sim_dir": str(sim_dir),
                "artifact_status": "backend_only",
                "success_failure_report_valid": True,
                "success_failure_report_rebuilt_from": str(_data_collection_path(sim_dir)),
                "report_generation_source": "post_backend_rebuild",
                "backend_stdout_tail": _read_text_tail(backend_log),
                "backend_stderr_tail": "",
                "backend_log_path": str(backend_log),
                "result_row": result_row,
            },
        )
        write_status(output_dir, payload)
        return payload
    except Exception as exc:
        snapshot = _artifact_snapshot(sim_dir, int(row["run_steps"]), output_dir / "success_failure_report.json")
        report_bad = stage in {"backend_only_reports", "backend_only_validate_report"}
        payload = _status_payload(
            row=row,
            row_index=row_index,
            status="partial_failed" if report_bad else ("partial_with_artifacts" if snapshot["sim_status_exists"] or snapshot["movement_count"] else "failed"),
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=expected_sim_dir,
            resolved_sim_dir=sim_dir if sim_dir.exists() else None,
            error=str(exc),
            traceback_text=traceback.format_exc(),
            stage="report_bad_after_backend_success" if report_bad else stage,
            scenario=scenario_info,
            extra={
                **snapshot,
                "success_failure_report_valid": False if report_bad else None,
                "success_failure_report_rebuilt_from": str(_data_collection_path(sim_dir)) if sim_dir.exists() else None,
                "report_generation_source": "post_backend_rebuild" if report_bad else None,
                "backend_stdout_tail": _read_text_tail(backend_log),
                "backend_stderr_tail": "",
                "backend_log_path": str(backend_log),
            },
        )
        write_status(output_dir, payload)
        return payload
    finally:
        if not finished_backend and proc is not None and proc.poll() is None:
            try:
                _finish_backend_process(target_sim, proc, timeout_seconds=20)
            except Exception:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
        if log_handle is not None:
            log_handle.close()


def _status_payload(
    *,
    row: dict[str, Any],
    row_index: int | None,
    status: str,
    target_sim: str,
    output_dir: Path,
    expected_sim_dir: Path,
    resolved_sim_dir: Path | None = None,
    error: str | None = None,
    traceback_text: str | None = None,
    stage: str,
    scenario: dict[str, Any] | None = None,
    result_keys: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "scenario_id": row["scenario_id"],
        "row_index": row_index,
        "status": status,
        "target_sim": target_sim,
        "expected_sim_dir": str(expected_sim_dir),
        "resolved_sim_dir": str(resolved_sim_dir) if resolved_sim_dir is not None else None,
        "output_dir": str(output_dir),
        "run_steps": int(row.get("run_steps", 0) or 0),
        "step_completed": None,
        "movement_count": None,
        "data_collection_exists": False,
        "sim_status_exists": False,
        "success_failure_report_exists": False,
        "error": error,
        "traceback": traceback_text,
        "stage": stage,
        "frontend_stdout_tail": "",
        "frontend_stderr_tail": "",
        "backend_stdout_tail": "",
        "backend_stderr_tail": "",
        "result_keys": result_keys or [],
        "scenario": scenario or {},
    }
    if extra:
        payload.update(extra)
    return payload


def run_one_scenario(
    *,
    row: dict[str, Any],
    output_root: str | Path,
    row_index: int | None = None,
    dry_run: bool = False,
    backend_only: bool = False,
    debug: bool = False,
) -> dict[str, Any]:
    output_dir = scenario_output_dir(output_root, row["scenario_id"])
    target_sim = f"cluster_taskB_{row['scenario_id']}"
    expected_sim_dir = (STORAGE_ROOT / target_sim).resolve()
    port = 9000 + int(row["seed"])
    scenario_info = {
        "scenario_id": row["scenario_id"],
        "staffing_profile": row["staffing_profile"],
        "hospital_profile": row["hospital_profile"],
        "load_factor": row["load_factor"],
        "seed": row["seed"],
        "doctor_count": row["doctor_count"],
        "nurse_count": row["nurse_count"],
        "run_steps": row["run_steps"],
        "time_scale_minutes_per_step": row["time_scale_minutes_per_step"],
        "port": port,
        "target_sim": target_sim,
        "output_dir": str(output_dir),
    }
    if dry_run:
        payload = _status_payload(
            row=row,
            row_index=row_index,
            status="dry_run",
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=expected_sim_dir,
            resolved_sim_dir=expected_sim_dir,
            stage="dry_run",
            scenario=scenario_info,
        )
        write_status(output_dir, payload)
        return payload

    if backend_only:
        return _run_backend_only(
            row=row,
            scenario_info=scenario_info,
            output_dir=output_dir,
            expected_sim_dir=expected_sim_dir,
            row_index=row_index,
            debug=debug,
        )

    config = load_yaml(CONFIG_PATH)
    profiles = load_profiles(PROFILES_PATH)
    profile = dict(profiles[row["hospital_profile"]])
    profile["doctor_count"] = int(row["doctor_count"])
    profile["nurse_count"] = int(row["nurse_count"])

    result_keys: list[str] = []
    resolved_sim_dir: Path | None = None
    stage = "starting"
    smoke_summary: Any = None
    try:
        minutes_per_step = validate_minutes_per_step(config, int(row["time_scale_minutes_per_step"]))
        stage = "run_smoke"
        smoke_summary = run_smoke(
            port=port,
            origin="ed_sim_n5",
            target=target_sim,
            run_steps=int(row["run_steps"]),
            max_attempts=3,
            settings_overrides={
                **build_settings_overrides(
                    profile_name=row["hospital_profile"],
                    profile=profile,
                    load_factor=float(row["load_factor"]),
                    seed=int(row["seed"]),
                    minutes_per_step=minutes_per_step,
                    config=config,
                ),
                "background_arrival_enabled": False,
                "patient_rate_modifier": 0,
            },
        )
        result_keys = _safe_result_keys(smoke_summary)
        print(f"DEBUG runner result keys: {result_keys}", file=sys.stderr)
        target_sim = _target_sim_from_result(smoke_summary, target_sim)
        resolved_sim_dir = _resolve_sim_dir_from_result(smoke_summary, target_sim)
        if isinstance(smoke_summary, dict) and smoke_summary.get("status") != "success":
            raise RuntimeError(
                "run_smoke did not complete successfully: "
                f"status={smoke_summary.get('status')!r}, "
                f"failure_stage={smoke_summary.get('failure_stage')!r}, "
                f"error={smoke_summary.get('error')!r}, "
                f"missing_fields={smoke_summary.get('missing_fields')!r}"
            )
        sim_dir = resolved_sim_dir
        stage = "runtime_evidence_report"
        preload_patient_count = round(int(profile["normal_patient_count"]) * float(row["load_factor"]))
        output_dir.mkdir(parents=True, exist_ok=True)
        probe_report = build_runtime_evidence_report(
            sim_dir=sim_dir,
            output_path=output_dir / "runtime_evidence_probe_report.json",
            hospital_profile=row["hospital_profile"],
            load_factor=float(row["load_factor"]),
            preload_patient_count=preload_patient_count,
            run_steps_requested=int(row["run_steps"]),
        )
        probe_envelope = {
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
        }
        probe_envelope_path = output_dir / "probe_envelope.json"
        probe_envelope_path.write_text(json.dumps(probe_envelope, indent=2, ensure_ascii=False), encoding="utf-8")

        stage = "metric_calibration_report"
        calibration = build_metric_calibration_report(
            sim_dir=sim_dir,
            probe_report_path=probe_envelope_path,
            composition_output_path=output_dir / "failure_composition_report.json",
            sensitivity_output_path=output_dir / "metric_sensitivity_report.json",
            calibrated_output_path=output_dir / "success_failure_report.json",
            summary_output_path=output_dir / "metric_calibration_summary.md",
        )
        calibrated_report = calibration["success_failure_report_calibrated"]
        validate_success_failure_report(calibrated_report)
        payload = _status_payload(
            row=row,
            row_index=row_index,
            status="success",
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=expected_sim_dir,
            resolved_sim_dir=sim_dir,
            stage="completed",
            scenario=scenario_info,
            result_keys=result_keys,
            extra={
                "sim_dir": str(sim_dir),
                "artifact_status": "newly_run",
                "success_failure_report_valid": True,
                "success_failure_report_rebuilt_from": str(_data_collection_path(sim_dir)),
                "report_generation_source": "post_backend_rebuild",
                "result_row": _result_row_from_report(
                    row=row,
                    profile=profile,
                    preload_patient_count=preload_patient_count,
                    report=calibrated_report,
                    failure_composition_report=calibration.get("failure_composition_report"),
                    sim_dir=sim_dir,
                    target_sim=target_sim,
                    artifact_status="newly_run",
                ),
            },
        )
    except Exception as exc:
        payload = _status_payload(
            row=row,
            row_index=row_index,
            status="failed",
            target_sim=target_sim,
            output_dir=output_dir,
            expected_sim_dir=expected_sim_dir,
            resolved_sim_dir=resolved_sim_dir if resolved_sim_dir is not None else (expected_sim_dir if expected_sim_dir.exists() else None),
            error=str(exc),
            traceback_text=traceback.format_exc(),
            stage=stage,
            scenario=scenario_info,
            result_keys=result_keys,
            extra={
                "runner_status": smoke_summary.get("status") if isinstance(smoke_summary, dict) else None,
                "runner_error": smoke_summary.get("error") if isinstance(smoke_summary, dict) else None,
                "runner_failure_stage": smoke_summary.get("failure_stage") if isinstance(smoke_summary, dict) else None,
                "runner_missing_fields": smoke_summary.get("missing_fields") if isinstance(smoke_summary, dict) else None,
            },
        )

    write_status(output_dir, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Task B cluster scenario in headless mode.")
    parser.add_argument("--scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--scenario-row", dest="scenario_csv_alias", default=None)
    parser.add_argument("--row-index", type=int, required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_csv = args.scenario_csv_alias or args.scenario_csv
    row = read_scenario_row(scenario_csv, args.row_index)
    result = run_one_scenario(
        row=row,
        output_root=args.output_root,
        row_index=args.row_index,
        dry_run=bool(args.dry_run),
        backend_only=bool(args.backend_only),
        debug=bool(args.debug),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
