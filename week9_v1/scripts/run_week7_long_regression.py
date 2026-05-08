import argparse
import copy
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import math
from datetime import datetime, timedelta
from json import JSONDecodeError
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = REPO_ROOT / "environment" / "frontend_server"
BACKEND_ROOT = REPO_ROOT / "reverie" / "backend_server"
ANALYSIS_ROOT = REPO_ROOT / "analysis"
STORAGE_ROOT = FRONTEND_ROOT / "storage"
COMPRESSED_ROOT = FRONTEND_ROOT / "compressed_storage"
TEMP_ROOT = FRONTEND_ROOT / "temp_storage"
BASE_SEED = STORAGE_ROOT / "ed_sim_n5"
SCENARIO_ROOT = ANALYSIS_ROOT / "scenario_regressions"
KEY_METRICS = (
    "max_current_patients",
    "max_doctor_global_queue",
    "max_triage_queue",
    "max_imaging_waiting",
    "max_boarding_timeout_events",
)
TRACE_METRICS = (
    "current_patients",
    "doctor_global_queue",
    "triage_queue",
    "imaging_waiting",
    "boarding_timeout_events",
)


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path, default=None, retries: int = 8, delay_seconds: float = 0.2):
    if not path.exists():
        return default
    last_error = None
    for attempt in range(retries):
        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                raise JSONDecodeError("empty file", raw, 0)
            return json.loads(raw)
        except (JSONDecodeError, OSError, PermissionError) as exc:
            last_error = exc
            if attempt == retries - 1:
                if default is not None:
                    return default
                raise
            time.sleep(delay_seconds * (attempt + 1))
    if default is not None:
        return default
    raise last_error


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _safe_float(raw_value):
    if raw_value in (None, "", "None"):
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _load_csv_rows(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _safe_int(raw_value):
    if raw_value in (None, "", "None"):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        try:
            return int(float(raw_value))
        except (TypeError, ValueError):
            return None


def reset_temp_storage(temp_root: Path):
    temp_root.mkdir(parents=True, exist_ok=True)
    commands_dir = temp_root / "commands"
    if commands_dir.exists():
        shutil.rmtree(commands_dir, ignore_errors=True)
    commands_dir.mkdir(parents=True, exist_ok=True)
    for name in ["curr_step.json", "curr_sim_code.json", "sim_output.json"]:
        path = temp_root / name
        if path.exists():
            for _ in range(10):
                try:
                    path.unlink()
                    break
                except PermissionError:
                    time.sleep(0.2)


def copy_seed_folder(origin_name: str) -> Path:
    origin_dir = STORAGE_ROOT / origin_name
    if origin_dir.exists():
        shutil.rmtree(origin_dir, ignore_errors=True)
    shutil.copytree(BASE_SEED, origin_dir)
    return origin_dir


def update_meta(origin_dir: Path, updates: dict):
    meta_path = origin_dir / "reverie" / "meta.json"
    meta = read_json(meta_path, default={}) or {}
    meta.update(updates)
    write_json(meta_path, meta)


def seed_boarding_timeout(origin_dir: Path):
    scratch_path = origin_dir / "personas" / "Patient 1" / "bootstrap_memory" / "scratch.json"
    scratch = read_json(scratch_path, default={}) or {}
    scratch.update(
        {
            "state": "ADMITTED_BOARDING",
            "admitted_to_hospital": True,
            "admission_boarding_start": "January 01, 2024, 09:50:00",
            "admission_boarding_end": "January 01, 2024, 12:30:00",
            "boarding_timeout_recorded": False,
            "boarding_timeout_at": None,
            "assigned_doctor": None,
            "time_to_next": None,
            "next_step": "ed map:emergency department:major injuries zone:bed",
            "next_room": "major injuries zone",
            "CTAS": scratch.get("CTAS") or 2,
            "injuries_zone": scratch.get("injuries_zone") or "major injuries zone",
        }
    )
    write_json(scratch_path, scratch)


def seed_imaging_bottleneck(origin_dir: Path):
    patient_defs = [
        ("Patient 1", "major injuries zone", [8, 8]),
        ("Patient 2", "minor injuries zone", [10, 8]),
    ]
    env_path = origin_dir / "environment" / "0.json"
    env = read_json(env_path, default={}) or {}
    for patient_name, zone, bed_assignment in patient_defs:
        scratch_path = origin_dir / "personas" / patient_name / "bootstrap_memory" / "scratch.json"
        scratch = read_json(scratch_path, default={}) or {}
        scratch.update(
            {
                "state": "WAITING_FOR_TEST",
                "testing_kind": "imaging",
                "time_to_next": None,
                "assigned_doctor": None,
                "in_queue": False,
                "next_room": "diagnostic room",
                "next_step": "ed map:emergency department:diagnostic room:diagnostic table",
                "CTAS": 2,
                "injuries_zone": zone,
                "bed_assignment": bed_assignment,
                "testing_end_time": None,
            }
        )
        write_json(scratch_path, scratch)
        env.setdefault(patient_name, {"maze": "Emergency Department", "x": bed_assignment[0], "y": bed_assignment[1]})
    write_json(env_path, env)


def resolve_runtime_env(
    execution_profile: str,
    *,
    llm_mode: str | None = None,
    embedding_mode: str | None = None,
):
    profile = (execution_profile or "deep_fast").strip().lower()
    if profile == "deep_fast":
        return {
            "LLM_MODE": "local_only",
            "EMBEDDING_MODE": "local_only",
            "USE_LOCAL_EMBEDDINGS": "1",
        }
    if profile == "realism_check":
        resolved_llm_mode = (llm_mode or "remote_only").strip().lower() or "remote_only"
        resolved_embedding_mode = (embedding_mode or "hybrid").strip().lower() or "hybrid"
        return {
            "LLM_MODE": resolved_llm_mode,
            "EMBEDDING_MODE": resolved_embedding_mode,
            "USE_LOCAL_EMBEDDINGS": "1" if resolved_embedding_mode == "local_only" else "0",
        }
    raise ValueError(f"Unsupported execution profile: {execution_profile}")


def launch_backend(
    origin_name: str,
    target_name: str,
    log_path: Path,
    temp_root: Path,
    runtime_env_overrides: dict | None = None,
):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    env = dict(os.environ)
    env["EDSIM_TEMP_DIR"] = str(temp_root)
    for key, value in (runtime_env_overrides or {}).items():
        env[str(key)] = str(value)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "reverie.py",
            "--origin",
            origin_name,
            "--target",
            target_name,
            "--frontend_ui",
            "yes",
            "--browser",
            "no",
            "--headless",
            "yes",
            "--write_movement",
            "yes",
        ],
        cwd=str(BACKEND_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return proc, log_file


def wait_for_boot(target_name: str, temp_root: Path, timeout_seconds: int = 120):
    deadline = time.time() + timeout_seconds
    curr_sim_path = temp_root / "curr_sim_code.json"
    curr_step_path = temp_root / "curr_step.json"
    while time.time() < deadline:
        sim_payload = read_json(curr_sim_path, default={}) or {}
        step_payload = read_json(curr_step_path, default={}) or {}
        if sim_payload.get("sim_code") == target_name and "step" in step_payload:
            return int(step_payload["step"])
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for backend boot for {target_name}")


def send_command(command: str, temp_root: Path):
    commands_dir = temp_root / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    command_id = str(int(time.time() * 1000))
    payload = {
        "id": command_id,
        "command": command,
        "created_at": datetime.utcnow().isoformat(),
    }
    final_path = commands_dir / f"cmd_{command_id}.json"
    temp_path = commands_dir / f"cmd_{command_id}.json.tmp"
    write_json(temp_path, payload)
    temp_path.replace(final_path)
    return command_id


def wait_for_step(expected_step: int, proc: subprocess.Popen, temp_root: Path, timeout_seconds: int):
    deadline = time.time() + timeout_seconds
    curr_step_path = temp_root / "curr_step.json"
    last_seen = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Backend exited early with code {proc.returncode}")
        payload = read_json(curr_step_path, default={}) or {}
        if "step" in payload:
            last_seen = int(payload["step"])
            if last_seen >= expected_step:
                return last_seen
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for step {expected_step}; last_seen={last_seen}")


def sample_status(target_dir: Path):
    status_path = target_dir / "sim_status.json"
    status = read_json(status_path, default={}) or {}
    movement_files = len(list((target_dir / "movement").glob("*.json"))) if (target_dir / "movement").exists() else 0
    environment_files = len(list((target_dir / "environment").glob("*.json"))) if (target_dir / "environment").exists() else 0
    return {
        "sampled_at": now_stamp(),
        "status": status,
        "movement_files": movement_files,
        "environment_files": environment_files,
    }


def run_analysis(sim_code: str, scenario_report_dir: Path):
    result = subprocess.run(
        [sys.executable, "compute_metrics.py", "--sim", sim_code, "--refresh-compressed"],
        cwd=str(ANALYSIS_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    analysis_report = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    write_json(scenario_report_dir / "analysis_run.json", analysis_report)
    for name in ["patient_time_metrics.csv", "ctas_daily_metrics.csv", "resource_event_metrics.json"]:
        source = ANALYSIS_ROOT / name
        if source.exists():
            shutil.copy2(source, scenario_report_dir / name)


def data_collection_counts(target_dir: Path):
    data_collection = read_json(target_dir / "reverie" / "data_collection.json", default={}) or {}
    patients = data_collection.get("Patient", {}) or {}
    timeout_events = 0
    admitted = 0
    for patient_payload in patients.values():
        if (patient_payload.get("boarding_timeout_event") or {}).get("occurred"):
            timeout_events += 1
        if (patient_payload.get("admitted_to_hospital") or {}).get("occurred"):
            admitted += 1
    return {
        "patient_records": len(patients),
        "boarding_timeout_events": timeout_events,
        "admitted_patients": admitted,
    }


def summarise_samples(samples):
    summary = {
        "max_current_patients": 0,
        "max_total_patients": 0,
        "max_triage_queue": 0,
        "max_doctor_global_queue": 0,
        "max_lab_waiting": 0,
        "max_imaging_waiting": 0,
        "max_boarding_timeout_events": 0,
    }
    for sample in samples:
        status = sample.get("status", {})
        queues = status.get("queues", {})
        resources = status.get("resources", {})
        summary["max_current_patients"] = max(summary["max_current_patients"], int(status.get("current_patients", 0) or 0))
        summary["max_total_patients"] = max(summary["max_total_patients"], int(status.get("total_patients", 0) or 0))
        summary["max_triage_queue"] = max(summary["max_triage_queue"], int(queues.get("triage", 0) or 0))
        summary["max_doctor_global_queue"] = max(summary["max_doctor_global_queue"], int(queues.get("doctor_global", 0) or 0))
        summary["max_lab_waiting"] = max(summary["max_lab_waiting"], int(queues.get("lab_waiting", 0) or 0))
        summary["max_imaging_waiting"] = max(summary["max_imaging_waiting"], int(queues.get("imaging_waiting", 0) or 0))
        summary["max_boarding_timeout_events"] = max(summary["max_boarding_timeout_events"], int(resources.get("boarding_timeout_events", 0) or 0))
    return summary


def extract_key_metrics(result: dict):
    sample_summary = result.get("sample_summary", {}) or {}
    return {
        metric: int(sample_summary.get(metric, 0) or 0)
        for metric in KEY_METRICS
    }


def summarise_metric_snapshots(metric_snapshots: list[dict]):
    if not metric_snapshots:
        return {}
    summary = {}
    for metric in KEY_METRICS:
        values = [int(snapshot.get(metric, 0) or 0) for snapshot in metric_snapshots]
        summary[metric] = {
            "values": values,
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
        }
    return summary


def diff_metric_snapshots(reference: dict, other: dict):
    diffs = {}
    for metric in KEY_METRICS:
        ref_value = int(reference.get(metric, 0) or 0)
        other_value = int(other.get(metric, 0) or 0)
        diffs[metric] = abs(other_value - ref_value)
    return diffs


def build_analysis_artifact_summary(scenario_report_dir: Path):
    patient_rows = _load_csv_rows(scenario_report_dir / "patient_time_metrics.csv")
    ctas_rows = _load_csv_rows(scenario_report_dir / "ctas_daily_metrics.csv")
    resource_metrics = read_json(scenario_report_dir / "resource_event_metrics.json", default={}) or {}

    patient_counts_by_ctas = {}
    testing_kind_counts = {}
    wait_values = []
    total_ed_values = []
    boarding_timeout_count = 0

    for row in patient_rows:
        ctas_level = str(row.get("ctas_level") or "").strip()
        if ctas_level:
            patient_counts_by_ctas[ctas_level] = patient_counts_by_ctas.get(ctas_level, 0) + 1
        testing_kind = str(row.get("testing_kind") or "").strip()
        if testing_kind:
            testing_kind_counts[testing_kind] = testing_kind_counts.get(testing_kind, 0) + 1
        wait_value = _safe_float(row.get("wait_minutes"))
        if wait_value is not None:
            wait_values.append(wait_value)
        total_value = _safe_float(row.get("total_ed_minutes"))
        if total_value is not None:
            total_ed_values.append(total_value)
        if str(row.get("boarding_timeout_occurred")).lower() == "true":
            boarding_timeout_count += 1

    ctas_summary = {}
    for row in ctas_rows:
        ctas_key = str(row.get("ctas_level") or "").strip()
        if not ctas_key:
            continue
        ctas_summary[ctas_key] = {
            "patients": int(float(row.get("patients") or 0)),
            "avg_wait_minutes": _safe_float(row.get("avg_wait_minutes")),
            "median_wait_minutes": _safe_float(row.get("median_wait_minutes")),
            "avg_treatment_minutes": _safe_float(row.get("avg_treatment_minutes")),
            "median_treatment_minutes": _safe_float(row.get("median_treatment_minutes")),
            "avg_total_ed_minutes": _safe_float(row.get("avg_total_ed_minutes")),
            "median_total_ed_minutes": _safe_float(row.get("median_total_ed_minutes")),
        }

    patient_summary = {
        "patient_rows": len(patient_rows),
        "patient_counts_by_ctas": patient_counts_by_ctas,
        "testing_kind_counts": testing_kind_counts,
        "boarding_timeout_count": boarding_timeout_count,
        "avg_wait_minutes_overall": (sum(wait_values) / len(wait_values)) if wait_values else None,
        "avg_total_ed_minutes_overall": (sum(total_ed_values) / len(total_ed_values)) if total_ed_values else None,
    }

    return {
        "patient_time_metrics_rows": patient_rows,
        "patient_metrics": patient_summary,
        "ctas_metrics": ctas_summary,
        "resource_metrics": resource_metrics,
    }


def flatten_numeric_values(payload, prefix=""):
    flattened = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_numeric_values(value, child_prefix))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            child_prefix = f"{prefix}[{index}]"
            flattened.update(flatten_numeric_values(value, child_prefix))
    elif isinstance(payload, (int, float)) and not isinstance(payload, bool):
        flattened[prefix] = float(payload)
    return flattened


def summarise_flattened_numeric_snapshots(snapshots: list[dict]):
    if not snapshots:
        return {}
    keys = sorted({key for snapshot in snapshots for key in snapshot.keys()})
    summary = {}
    for key in keys:
        values = [snapshot[key] for snapshot in snapshots if key in snapshot]
        if not values:
            continue
        summary[key] = {
            "values": values,
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
        }
    return summary


def diff_flattened_numeric_snapshots(reference: dict, other: dict):
    diffs = {}
    for key in sorted(set(reference.keys()) | set(other.keys())):
        diffs[key] = abs(float(other.get(key, 0.0)) - float(reference.get(key, 0.0)))
    return diffs


def build_trace_series(result: dict):
    series = []
    for sample in result.get("samples", []) or []:
        status = sample.get("status", {}) or {}
        queues = status.get("queues", {}) or {}
        resources = status.get("resources", {}) or {}
        series.append(
            {
                "step": int(sample.get("observed_step", status.get("step", 0)) or 0),
                "current_patients": int(status.get("current_patients", 0) or 0),
                "doctor_global_queue": int(queues.get("doctor_global", 0) or 0),
                "triage_queue": int(queues.get("triage", 0) or 0),
                "imaging_waiting": int(queues.get("imaging_waiting", 0) or 0),
                "boarding_timeout_events": int(resources.get("boarding_timeout_events", 0) or 0),
            }
        )
    return series


def compare_trace_series(reference_series: list[dict], other_series: list[dict]):
    aligned_points = min(len(reference_series), len(other_series))
    metric_diffs = {}
    for metric in TRACE_METRICS:
        diffs = []
        for index in range(aligned_points):
            diffs.append(
                abs(
                    int(reference_series[index].get(metric, 0) or 0)
                    - int(other_series[index].get(metric, 0) or 0)
                )
            )
        metric_diffs[metric] = {
            "aligned_points": aligned_points,
            "max_abs_diff": max(diffs) if diffs else 0,
            "sum_abs_diff": sum(diffs) if diffs else 0,
        }
    return {
        "reference_points": len(reference_series),
        "other_points": len(other_series),
        "aligned_points": aligned_points,
        "metrics": metric_diffs,
    }


def compare_patient_time_rows(reference_rows: list[dict], other_rows: list[dict]):
    reference_by_patient = {row.get("patient"): row for row in reference_rows if row.get("patient")}
    other_by_patient = {row.get("patient"): row for row in other_rows if row.get("patient")}

    shared_patients = sorted(set(reference_by_patient) & set(other_by_patient))
    only_reference = sorted(set(reference_by_patient) - set(other_by_patient))
    only_other = sorted(set(other_by_patient) - set(reference_by_patient))

    numeric_fields = ("wait_minutes", "treatment_minutes", "total_ed_minutes")
    numeric_summary = {}
    for field in numeric_fields:
        diffs = []
        for patient in shared_patients:
            reference_value = _safe_float(reference_by_patient[patient].get(field))
            other_value = _safe_float(other_by_patient[patient].get(field))
            if reference_value is None or other_value is None:
                continue
            diffs.append(abs(other_value - reference_value))
        numeric_summary[field] = {
            "compared_patients": len(diffs),
            "max_abs_diff": max(diffs) if diffs else 0.0,
            "avg_abs_diff": (sum(diffs) / len(diffs)) if diffs else 0.0,
        }

    discrete_fields = ("ctas_level", "testing_kind", "boarding_timeout_occurred")
    discrete_summary = {}
    for field in discrete_fields:
        mismatch_patients = []
        for patient in shared_patients:
            if reference_by_patient[patient].get(field) != other_by_patient[patient].get(field):
                mismatch_patients.append(patient)
        discrete_summary[field] = {
            "mismatch_count": len(mismatch_patients),
            "mismatch_examples": mismatch_patients[:10],
        }

    return {
        "reference_patient_count": len(reference_rows),
        "other_patient_count": len(other_rows),
        "shared_patient_count": len(shared_patients),
        "patient_set_match": not only_reference and not only_other,
        "only_reference_patients": only_reference[:20],
        "only_other_patients": only_other[:20],
        "numeric_fields": numeric_summary,
        "discrete_fields": discrete_summary,
    }


def build_fine_grained_diff(reference_result: dict, other_result: dict):
    reference_rows = (reference_result.get("analysis_artifacts") or {}).get("patient_time_metrics_rows", []) or []
    other_rows = (other_result.get("analysis_artifacts") or {}).get("patient_time_metrics_rows", []) or []
    return {
        "patient_time_metrics": compare_patient_time_rows(reference_rows, other_rows),
        "sampled_status_trace": compare_trace_series(
            build_trace_series(reference_result),
            build_trace_series(other_result),
        ),
        "flattened_analysis_artifacts": diff_flattened_numeric_snapshots(
            flatten_numeric_values(reference_result.get("analysis_artifacts") or {}),
            flatten_numeric_values(other_result.get("analysis_artifacts") or {}),
        ),
    }


def configure_seed(config: dict, seed: int) -> dict:
    seeded_config = copy.deepcopy(config)
    meta_updates = copy.deepcopy(seeded_config.get("meta_updates", {}))
    meta_updates["seed"] = int(seed)
    seeded_config["meta_updates"] = meta_updates
    seeded_config["seed"] = int(seed)
    return seeded_config


def build_reproducibility_scenario_summary(
    scenario_name: str,
    same_seed_results: list[dict],
    cross_seed_results: list[dict],
    *,
    base_seed: int,
):
    same_seed_metrics = [extract_key_metrics(result) for result in same_seed_results]
    same_seed_reference = same_seed_metrics[0] if same_seed_metrics else {}
    same_seed_fine_metrics = [
        flatten_numeric_values((result.get("analysis_artifacts") or {}))
        for result in same_seed_results
    ]
    same_seed_fine_reference = same_seed_fine_metrics[0] if same_seed_fine_metrics else {}
    same_seed_pairwise_diffs = []
    for repeat_index, result in enumerate(same_seed_results[1:], start=2):
        same_seed_pairwise_diffs.append(
            {
                "reference_repeat": 1,
                "other_repeat": repeat_index,
                "diff": build_fine_grained_diff(same_seed_results[0], result),
            }
        )
    cross_seed_summaries = []
    for result in cross_seed_results:
        metrics = extract_key_metrics(result)
        fine_metrics = flatten_numeric_values((result.get("analysis_artifacts") or {}))
        cross_seed_summaries.append(
            {
                "seed": int(result.get("meta_updates", {}).get("seed", 0) or 0),
                "passed": scenario_passed(result, required_steps=int(result.get("expected_total_steps", 0) or 0)),
                "metrics": metrics,
                "diff_vs_same_seed_reference": diff_metric_snapshots(same_seed_reference, metrics) if same_seed_reference else {},
                "analysis_artifacts": result.get("analysis_artifacts") or {},
                "fine_grained_diff_vs_same_seed_reference": diff_flattened_numeric_snapshots(same_seed_fine_reference, fine_metrics) if same_seed_fine_reference else {},
                "patient_resource_trace_diff_vs_same_seed_reference": build_fine_grained_diff(same_seed_results[0], result) if same_seed_results else {},
                "wall_clock_seconds": result.get("wall_clock_seconds"),
                "returncode": result.get("returncode"),
                "error": result.get("error"),
            }
        )

    return {
        "scenario": scenario_name,
        "same_seed": {
            "seed": int(base_seed),
            "runs": len(same_seed_results),
            "all_passed": all(
                scenario_passed(result, required_steps=int(result.get("expected_total_steps", 0) or 0))
                for result in same_seed_results
            ),
            "metrics": same_seed_metrics,
            "metric_spread": summarise_metric_snapshots(same_seed_metrics),
            "analysis_artifacts": [result.get("analysis_artifacts") or {} for result in same_seed_results],
            "fine_grained_metric_spread": summarise_flattened_numeric_snapshots(same_seed_fine_metrics),
            "pairwise_patient_resource_trace_diffs": same_seed_pairwise_diffs,
            "wall_clock_seconds": [result.get("wall_clock_seconds") for result in same_seed_results],
        },
        "different_seed": cross_seed_summaries,
        "different_seed_metric_spread": summarise_metric_snapshots(
            [entry["metrics"] for entry in cross_seed_summaries]
        ),
        "different_seed_fine_grained_metric_spread": summarise_flattened_numeric_snapshots(
            [
                flatten_numeric_values(entry.get("analysis_artifacts") or {})
                for entry in cross_seed_summaries
            ]
        ),
    }


def classify_runtime_log_flags(log_text: str) -> dict:
    normalized = str(log_text or "")
    curl_error_seen = "curl.exe failed" in normalized
    hybrid_fallback_recovered = any(
        marker in normalized
        for marker in (
            "llm safe request hybrid fallback",
            "llm safe legacy request hybrid fallback",
        )
    )
    return {
        "fail_safe_triggered": "FAIL SAFE TRIGGERED" in normalized,
        "curl_error_seen": curl_error_seen,
        "hybrid_fallback_recovered": hybrid_fallback_recovered,
        "curl_failed": curl_error_seen and not hybrid_fallback_recovered,
    }


def run_single_scenario(
    name: str,
    config: dict,
    report_dir: Path,
    *,
    runtime_env_overrides: dict | None = None,
    execution_profile: str | None = None,
):
    run_tag = report_dir.name
    origin_name = f"{name}-{run_tag}-origin"
    target_name = f"{name}-{run_tag}-run"
    origin_dir = copy_seed_folder(origin_name)
    target_dir = STORAGE_ROOT / target_name
    compressed_dir = COMPRESSED_ROOT / target_name
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    if compressed_dir.exists():
        shutil.rmtree(compressed_dir, ignore_errors=True)

    update_meta(origin_dir, config["meta_updates"])
    if config.get("seed_boarding_timeout"):
        seed_boarding_timeout(origin_dir)
    if config.get("seed_imaging_bottleneck"):
        seed_imaging_bottleneck(origin_dir)

    scenario_report_dir = report_dir / name
    scenario_report_dir.mkdir(parents=True, exist_ok=True)
    scenario_temp_root = report_dir / "_temp" / name
    reset_temp_storage(scenario_temp_root)
    proc, log_file = launch_backend(
        origin_name,
        target_name,
        scenario_report_dir / "runtime.log",
        scenario_temp_root,
        runtime_env_overrides=runtime_env_overrides,
    )
    samples = []
    error = None
    wall_start = time.perf_counter()
    try:
        current_step = wait_for_boot(target_name, scenario_temp_root)
        for chunk_index in range(config["chunks"]):
            chunk_steps = config["chunk_steps"]
            expected_step = current_step + chunk_steps
            send_command(f"run {chunk_steps}", scenario_temp_root)
            current_step = wait_for_step(expected_step, proc, scenario_temp_root, timeout_seconds=config["timeout_per_chunk_seconds"])
            sample = sample_status(target_dir)
            sample["chunk"] = chunk_index + 1
            sample["expected_step"] = expected_step
            sample["observed_step"] = current_step
            samples.append(sample)
        send_command("fin", scenario_temp_root)
        proc.wait(timeout=600)
    except Exception as exc:
        error = str(exc)
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait(timeout=30)
    finally:
        log_file.close()

    summary = {
        "scenario": name,
        "started_at": now_stamp(),
        "wall_clock_seconds": round(time.perf_counter() - wall_start, 3),
        "returncode": proc.returncode,
        "error": error,
        "meta_updates": config["meta_updates"],
        "samples": samples,
        "sample_summary": summarise_samples(samples),
        "data_collection": data_collection_counts(target_dir) if target_dir.exists() else {},
        "expected_total_steps": int(config["chunk_steps"] * config["chunks"]),
        "execution_profile": execution_profile,
        "runtime_env": runtime_env_overrides or {},
    }
    log_text = (scenario_report_dir / "runtime.log").read_text(encoding="utf-8", errors="replace") if (scenario_report_dir / "runtime.log").exists() else ""
    runtime_flags = classify_runtime_log_flags(log_text)
    summary["fail_safe_triggered"] = runtime_flags["fail_safe_triggered"]
    summary["curl_error_seen"] = runtime_flags["curl_error_seen"]
    summary["hybrid_fallback_recovered"] = runtime_flags["hybrid_fallback_recovered"]
    summary["curl_failed"] = runtime_flags["curl_failed"]
    if target_dir.exists():
        summary["final_status"] = read_json(target_dir / "sim_status.json", default={}) or {}
    write_json(scenario_report_dir / "summary.json", summary)
    if target_dir.exists():
        run_analysis(target_name, scenario_report_dir)
        summary["analysis_artifacts"] = build_analysis_artifact_summary(scenario_report_dir)
        write_json(scenario_report_dir / "summary.json", summary)
    return summary


def scenario_completed_steps(result: dict) -> int:
    samples = result.get("samples", []) or []
    if not samples:
        return 0
    return int(samples[-1].get("observed_step", 0) or 0)


def scenario_failed_reason(result: dict, required_steps: int | None = None) -> str | None:
    if result.get("returncode") not in (0, None):
        return f"backend_returncode={result.get('returncode')}"
    if result.get("error"):
        return str(result["error"])
    if result.get("fail_safe_triggered"):
        return "fail_safe_triggered"
    if result.get("curl_failed"):
        return "curl_failed"
    final_status = result.get("final_status", {}) or {}
    if not final_status:
        return "missing_final_status"
    if required_steps is not None and scenario_completed_steps(result) < int(required_steps):
        return f"insufficient_steps={scenario_completed_steps(result)}/{int(required_steps)}"
    return None


def scenario_passed(result: dict, required_steps: int | None = None) -> bool:
    return scenario_failed_reason(result, required_steps=required_steps) is None


def write_markdown_report(report_dir: Path, results: list):
    lines = [
        "# Week7 Long-run Regression Report",
        "",
        f"- Generated at: {now_stamp()}",
        f"- Report directory: `{report_dir}`",
        "",
    ]
    for result in results:
        sample_summary = result.get("sample_summary", {}) or {}
        data_collection = result.get("data_collection", {}) or {}
        lines.extend(
            [
                f"## {result['scenario']}",
                "",
                f"- Return code: `{result['returncode']}`",
                f"- Error: `{result['error']}`",
                f"- Wall-clock seconds: `{result.get('wall_clock_seconds')}`",
                f"- FAIL SAFE triggered: `{result.get('fail_safe_triggered')}`",
                f"- curl failed: `{result.get('curl_failed')}`",
                f"- Max current patients: `{sample_summary.get('max_current_patients', 0)}`",
                f"- Max total patients: `{sample_summary.get('max_total_patients', 0)}`",
                f"- Max triage queue: `{sample_summary.get('max_triage_queue', 0)}`",
                f"- Max doctor queue: `{sample_summary.get('max_doctor_global_queue', 0)}`",
                f"- Max lab waiting: `{sample_summary.get('max_lab_waiting', 0)}`",
                f"- Max imaging waiting: `{sample_summary.get('max_imaging_waiting', 0)}`",
                f"- Max boarding timeout events: `{sample_summary.get('max_boarding_timeout_events', 0)}`",
                f"- Data collection timeout events: `{data_collection.get('boarding_timeout_events', 0)}`",
                "",
            ]
        )
    (report_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def write_reproducibility_markdown(report_dir: Path, scenario_summaries: list[dict], meta: dict):
    lines = [
        "# Week7 Reproducibility Report",
        "",
        f"- Generated at: {now_stamp()}",
        f"- Execution profile: `{meta.get('execution_profile')}`",
        f"- Selected scenarios: `{', '.join(meta.get('selected_scenarios', []))}`",
        f"- Base seed: `{meta.get('seed')}`",
        f"- Repeats per same-seed scenario: `{meta.get('repeats')}`",
        f"- Compare seeds: `{meta.get('compare_seeds', [])}`",
        "",
    ]
    for scenario_summary in scenario_summaries:
        same_seed = scenario_summary.get("same_seed", {}) or {}
        lines.extend(
            [
                f"## {scenario_summary['scenario']}",
                "",
                f"- Same-seed all passed: `{same_seed.get('all_passed')}`",
                f"- Same-seed metric spread: `{json.dumps(same_seed.get('metric_spread', {}), ensure_ascii=False)}`",
                f"- Different-seed comparisons: `{json.dumps(scenario_summary.get('different_seed', []), ensure_ascii=False)}`",
                f"- Same-seed fine-grained spread: `{json.dumps(scenario_summary.get('same_seed', {}).get('fine_grained_metric_spread', {}), ensure_ascii=False)}`",
                f"- Different-seed fine-grained spread: `{json.dumps(scenario_summary.get('different_seed_fine_grained_metric_spread', {}), ensure_ascii=False)}`",
                "",
            ]
        )
    (report_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def scenario_catalog():
    common = {
        "step": 0,
        "seed": 1337,
        "fill_injuries": 0,
        "status_interval_steps": 1,
        "doctor_starting_amount": 1,
        "triage_starting_amount": 1,
        "bedside_starting_amount": 1,
    }
    return {
        "arrival_normal": {
            "meta_updates": {
                **common,
                "curr_time": "January 01, 2024, 07:00:00",
                "patient_rate_modifier": 4.0,
                "arrival_profile_mode": "normal",
                "surge_baseline_rate": 4.0,
                "surge_slowdown_scale": 0.0,
                "simulate_hospital_admission": False,
            },
            "chunk_steps": 1,
            "chunks": 12,
            "timeout_per_chunk_seconds": 900,
        },
        "arrival_surge": {
            "meta_updates": {
                **common,
                "curr_time": "January 01, 2024, 07:00:00",
                "patient_rate_modifier": 4.0,
                "arrival_profile_mode": "surge",
                "surge_baseline_rate": 4.0,
                "surge_slowdown_scale": 0.0,
                "simulate_hospital_admission": False,
            },
            "chunk_steps": 1,
            "chunks": 12,
            "timeout_per_chunk_seconds": 900,
        },
        "arrival_burst": {
            "meta_updates": {
                **common,
                "curr_time": "January 01, 2024, 07:00:00",
                "patient_rate_modifier": 4.0,
                "arrival_profile_mode": "burst",
                "surge_baseline_rate": 4.0,
                "surge_slowdown_scale": 0.0,
                "simulate_hospital_admission": False,
            },
            "chunk_steps": 1,
            "chunks": 12,
            "timeout_per_chunk_seconds": 900,
        },
        "bottleneck_imaging": {
            "meta_updates": {
                **common,
                "curr_time": "January 01, 2024, 11:00:00",
                "patient_rate_modifier": 1.5,
                "arrival_profile_mode": "surge",
                "surge_baseline_rate": 1.5,
                "surge_slowdown_scale": 0.0,
                "imaging_capacity": 1,
                "imaging_turnaround_minutes": 120,
                "lab_capacity": 2,
                "lab_turnaround_minutes": 30,
                "simulate_hospital_admission": False,
            },
            "seed_imaging_bottleneck": True,
            "chunk_steps": 1,
            "chunks": 4,
            "timeout_per_chunk_seconds": 900,
        },
        "boarding_timeout": {
            "meta_updates": {
                **common,
                "curr_time": "January 01, 2024, 10:00:00",
                "patient_rate_modifier": 1.0,
                "arrival_profile_mode": "normal",
                "simulate_hospital_admission": True,
                "boarding_timeout_minutes": 5,
                "admission_probability_by_ctas": {"1": 1.0, "2": 1.0, "3": 1.0, "4": 1.0, "5": 1.0},
                "admission_boarding_minutes_min": 60,
                "admission_boarding_minutes_max": 240,
            },
            "seed_boarding_timeout": True,
            "chunk_steps": 1,
            "chunks": 2,
            "timeout_per_chunk_seconds": 900,
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run long Week7 scenario regressions against the real auto-mode backend.")
    parser.add_argument(
        "--scenario",
        default="all",
        choices=[
            "all",
            "arrival",
            "bottleneck",
            "boarding_timeout",
            "arrival_normal",
            "arrival_surge",
            "arrival_burst",
            "bottleneck_imaging",
        ],
        help="Scenario group to run",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Optional override for the number of chunks to run per selected scenario.",
    )
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "smoke", "deep"],
        help="Run mode: smoke only, deep only, or auto smoke-first then deep.",
    )
    parser.add_argument(
        "--smoke-steps",
        type=int,
        default=7,
        help="Target steps for smoke runs before allowing deep mode.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Only meaningful with --mode deep; skips any smoke-first validation.",
    )
    parser.add_argument(
        "--execution-profile",
        default="deep_fast",
        choices=["deep_fast", "realism_check"],
        help="Execution profile. deep_fast = local-only long run, realism_check = remote/hybrid realism run.",
    )
    parser.add_argument(
        "--llm-mode",
        default=None,
        choices=["local_only", "remote_only", "hybrid"],
        help="Optional LLM mode override for the selected execution profile.",
    )
    parser.add_argument(
        "--embedding-mode",
        default=None,
        choices=["local_only", "remote_only", "hybrid"],
        help="Optional embedding mode override for the selected execution profile.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Seed override for reproducibility or direct deep runs.",
    )
    parser.add_argument(
        "--reproducibility",
        action="store_true",
        help="Run same-seed and different-seed reproducibility checks instead of the normal smoke/deep flow.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of repeated runs for same-seed reproducibility checks.",
    )
    parser.add_argument(
        "--compare-seed",
        dest="compare_seeds",
        type=int,
        action="append",
        default=[],
        help="Additional seed to compare against the base seed. Can be passed multiple times.",
    )
    return parser.parse_args()


def expand_selection(selection: str):
    if selection in {"arrival_normal", "arrival_surge", "arrival_burst", "bottleneck_imaging"}:
        return [selection]
    if selection == "arrival":
        return ["arrival_normal", "arrival_surge", "arrival_burst"]
    if selection == "bottleneck":
        return ["bottleneck_imaging"]
    if selection == "boarding_timeout":
        return ["boarding_timeout"]
    return ["arrival_normal", "arrival_surge", "arrival_burst", "bottleneck_imaging", "boarding_timeout"]


def configure_smoke_scenario(config: dict, smoke_steps: int) -> dict:
    smoke_config = copy.deepcopy(config)
    chunk_steps = int(smoke_config.get("chunk_steps", 1) or 1)
    smoke_config["chunks"] = max(1, int(math.ceil(float(smoke_steps) / float(chunk_steps))))
    smoke_config["smoke_target_steps"] = int(smoke_steps)
    return smoke_config


def configure_deep_scenario(config: dict, max_chunks: int | None = None) -> dict:
    deep_config = copy.deepcopy(config)
    if max_chunks is not None:
        deep_config["chunks"] = int(max_chunks)
    return deep_config


def run_scenario_batch(
    scenario_names: list[str],
    catalog: dict,
    report_dir: Path,
    *,
    batch_mode: str,
    smoke_steps: int | None = None,
    max_chunks: int | None = None,
    runtime_env_overrides: dict | None = None,
    execution_profile: str | None = None,
    seed: int | None = None,
):
    results = []
    for scenario_name in scenario_names:
        config = catalog[scenario_name]
        if batch_mode == "smoke":
            run_config = configure_smoke_scenario(config, smoke_steps=smoke_steps or 7)
        else:
            run_config = configure_deep_scenario(config, max_chunks=max_chunks)
        if seed is not None:
            run_config = configure_seed(run_config, seed)
        print(f"[{now_stamp()}] Running {batch_mode} scenario: {scenario_name}")
        result = run_single_scenario(
            scenario_name,
            run_config,
            report_dir,
            runtime_env_overrides=runtime_env_overrides,
            execution_profile=execution_profile,
        )
        result["run_mode"] = batch_mode
        results.append(result)
    write_json(report_dir / "summary.json", results)
    write_markdown_report(report_dir, results)
    return results


def run_reproducibility_flow(args):
    run_dir = SCENARIO_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    catalog = scenario_catalog()
    selected = expand_selection(args.scenario)
    runtime_env = resolve_runtime_env(
        args.execution_profile,
        llm_mode=args.llm_mode,
        embedding_mode=args.embedding_mode,
    )

    same_seed_results = []
    different_seed_results = []
    scenario_summaries = []

    for scenario_name in selected:
        scenario_same_seed_results = []
        for repeat_index in range(int(args.repeats)):
            report_dir = run_dir / "same_seed" / scenario_name / f"seed_{int(args.seed)}_repeat_{repeat_index + 1}"
            report_dir.mkdir(parents=True, exist_ok=True)
            run_config = configure_deep_scenario(catalog[scenario_name], max_chunks=args.max_chunks)
            run_config = configure_seed(run_config, args.seed)
            print(
                f"[{now_stamp()}] Running reproducibility same-seed scenario: "
                f"{scenario_name} seed={int(args.seed)} repeat={repeat_index + 1}"
            )
            result = run_single_scenario(
                scenario_name,
                run_config,
                report_dir,
                runtime_env_overrides=runtime_env,
                execution_profile=args.execution_profile,
            )
            result["run_mode"] = "reproducibility_same_seed"
            result["repeat_index"] = repeat_index + 1
            same_seed_results.append(result)
            scenario_same_seed_results.append(result)

        scenario_cross_seed_results = []
        for compare_seed in args.compare_seeds:
            report_dir = run_dir / "different_seed" / scenario_name / f"seed_{int(compare_seed)}"
            report_dir.mkdir(parents=True, exist_ok=True)
            run_config = configure_deep_scenario(catalog[scenario_name], max_chunks=args.max_chunks)
            run_config = configure_seed(run_config, compare_seed)
            print(
                f"[{now_stamp()}] Running reproducibility cross-seed scenario: "
                f"{scenario_name} seed={int(compare_seed)}"
            )
            result = run_single_scenario(
                scenario_name,
                run_config,
                report_dir,
                runtime_env_overrides=runtime_env,
                execution_profile=args.execution_profile,
            )
            result["run_mode"] = "reproducibility_different_seed"
            different_seed_results.append(result)
            scenario_cross_seed_results.append(result)

        scenario_summaries.append(
            build_reproducibility_scenario_summary(
                scenario_name,
                scenario_same_seed_results,
                scenario_cross_seed_results,
                base_seed=args.seed,
            )
        )

    summary = {
        "generated_at": now_stamp(),
        "scenario_selection": args.scenario,
        "selected_scenarios": selected,
        "execution_profile": args.execution_profile,
        "runtime_env": runtime_env,
        "seed": int(args.seed),
        "repeats": int(args.repeats),
        "compare_seeds": [int(seed) for seed in args.compare_seeds],
        "max_chunks": args.max_chunks,
        "same_seed_results": same_seed_results,
        "different_seed_results": different_seed_results,
        "scenario_summaries": scenario_summaries,
        "all_runs_passed": all(
            scenario_passed(result, required_steps=int(result.get("expected_total_steps", 0) or 0))
            for result in (same_seed_results + different_seed_results)
        ),
    }
    write_json(run_dir / "summary.json", summary)
    write_reproducibility_markdown(run_dir, scenario_summaries, summary)
    return (0 if summary["all_runs_passed"] else 1), summary, run_dir


def run_regression_flow(args):
    run_dir = SCENARIO_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    catalog = scenario_catalog()
    selected = expand_selection(args.scenario)
    runtime_env = resolve_runtime_env(
        args.execution_profile,
        llm_mode=args.llm_mode,
        embedding_mode=args.embedding_mode,
    )

    overall_summary = {
        "generated_at": now_stamp(),
        "scenario_selection": args.scenario,
        "selected_scenarios": selected,
        "run_mode": args.mode,
        "execution_profile": args.execution_profile,
        "runtime_env": runtime_env,
        "smoke_steps": int(args.smoke_steps),
        "skip_smoke": bool(args.skip_smoke),
        "smoke_passed": None,
        "smoke_failed_reason": None,
        "deep_started": False,
        "deep_completed": False,
        "smoke_results": [],
        "deep_results": [],
    }

    if args.mode in {"auto", "smoke"}:
        smoke_dir = run_dir / "smoke"
        smoke_dir.mkdir(parents=True, exist_ok=True)
        smoke_results = run_scenario_batch(
            selected,
            catalog,
            smoke_dir,
            batch_mode="smoke",
            smoke_steps=args.smoke_steps,
            runtime_env_overrides=runtime_env,
            execution_profile=args.execution_profile,
            seed=args.seed,
        )
        overall_summary["smoke_results"] = smoke_results
        failed_result = next(
            (
                result for result in smoke_results
                if not scenario_passed(result, required_steps=int(args.smoke_steps))
            ),
            None,
        )
        if failed_result is None:
            overall_summary["smoke_passed"] = True
        else:
            overall_summary["smoke_passed"] = False
            overall_summary["smoke_failed_reason"] = (
                f"{failed_result['scenario']}: "
                f"{scenario_failed_reason(failed_result, required_steps=int(args.smoke_steps))}"
            )
            if args.mode == "auto":
                write_json(run_dir / "summary.json", overall_summary)
                return 1, overall_summary, run_dir
    elif args.mode == "deep":
        overall_summary["smoke_passed"] = None

    if args.mode == "deep" and args.skip_smoke:
        overall_summary["smoke_failed_reason"] = "deep mode explicitly skipped smoke"

    if args.mode in {"auto", "deep"}:
        overall_summary["deep_started"] = True
        deep_dir = run_dir / "deep"
        deep_dir.mkdir(parents=True, exist_ok=True)
        deep_results = run_scenario_batch(
            selected,
            catalog,
            deep_dir,
            batch_mode="deep",
            max_chunks=args.max_chunks,
            runtime_env_overrides=runtime_env,
            execution_profile=args.execution_profile,
            seed=args.seed,
        )
        overall_summary["deep_results"] = deep_results
        overall_summary["deep_completed"] = all(
            scenario_passed(result, required_steps=int(result.get("expected_total_steps", 0) or 0))
            for result in deep_results
        )

    write_json(run_dir / "summary.json", overall_summary)
    if args.mode == "smoke":
        exit_code = 0 if overall_summary["smoke_passed"] else 1
    elif args.mode == "deep":
        exit_code = 0 if overall_summary["deep_completed"] else 1
    else:
        exit_code = 0 if overall_summary["smoke_passed"] and overall_summary["deep_completed"] else 1
    return exit_code, overall_summary, run_dir


def main():
    args = parse_args()
    if args.reproducibility:
        exit_code, summary, run_dir = run_reproducibility_flow(args)
    else:
        exit_code, summary, run_dir = run_regression_flow(args)
    print(f"[{now_stamp()}] Wrote scenario evidence to {run_dir}")
    if summary.get("smoke_failed_reason"):
        print(f"[{now_stamp()}] Smoke gate: {summary['smoke_failed_reason']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
