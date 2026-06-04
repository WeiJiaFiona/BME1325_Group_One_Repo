#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis"
for _path in (str(REPO_ROOT), str(ANALYSIS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from analysis.failure_report import write_failure_report


REQUIRED_RESOURCE_FIELDS = (
    "total_arrived_patients",
    "failed_patients_count",
    "failure_rate",
    "system_failed",
    "failure_threshold",
    "system_failed_comparator",
    "failure_reason_counts",
    "lwbs_count",
    "boarding_timeout_count",
    "ctas_target_wait_violation_count",
    "ed_los_over_threshold_count",
    "queue_overflow_exposure_count",
    "severe_trauma_time_to_surgery_violation_count",
    "critical_outcome_event_count",
)

REQUIRED_SYSTEM_HEALTH_FIELDS = (
    "failed",
    "failed_reason",
    "failure_rate",
    "failed_at_step",
)


def _resolve_pointer_path(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.is_file():
        try:
            candidate = Path(path.read_text(encoding="utf-8").strip())
            if candidate.exists():
                return candidate
        except Exception:
            pass
    return path


FRONTEND_ROOT = REPO_ROOT / "environment" / "frontend_server"
STORAGE_ROOT = _resolve_pointer_path(FRONTEND_ROOT / "storage")
TEMP_ROOT = _resolve_pointer_path(Path(os.environ.get("EDSIM_TEMP_DIR", str(FRONTEND_ROOT / "temp_storage"))))
BACKEND_DIR = REPO_ROOT / "reverie" / "backend_server"
DOC_PATH = REPO_ROOT / "docs" / "week13_runtime_smoke_debug.md"
RUNTIME_LOG_DIR = REPO_ROOT / "runtime_data" / "logs"


@dataclass
class AttemptConfig:
    attempt_id: int
    strategy: str
    headless: bool
    bootstrap_environment_from_movement: bool
    wait_seconds: int


def required_failure_field_paths() -> list[str]:
    return [f"resources.{field}" for field in REQUIRED_RESOURCE_FIELDS] + [
        f"system_health.{field}" for field in REQUIRED_SYSTEM_HEALTH_FIELDS
    ]


def find_missing_failure_fields(status_payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    resources = status_payload.get("resources")
    system_health = status_payload.get("system_health")
    if not isinstance(resources, dict):
        missing.extend([f"resources.{field}" for field in REQUIRED_RESOURCE_FIELDS])
    else:
        for field in REQUIRED_RESOURCE_FIELDS:
            if field not in resources:
                missing.append(f"resources.{field}")
    if not isinstance(system_health, dict):
        missing.extend([f"system_health.{field}" for field in REQUIRED_SYSTEM_HEALTH_FIELDS])
    else:
        for field in REQUIRED_SYSTEM_HEALTH_FIELDS:
            if field not in system_health:
                missing.append(f"system_health.{field}")
    return missing


def build_run_command_payload(run_steps: int) -> dict[str, str]:
    return {"command": f"run {int(run_steps)}"}


def resolve_target_sim_dir(storage_root: Path, target: str) -> Path:
    candidate = storage_root / target
    if candidate.exists():
        return candidate
    matching = sorted(
        [path for path in storage_root.glob(f"{target}*") if path.is_dir()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if matching:
        return matching[0]
    raise FileNotFoundError(f"Target sim directory not found for target={target}")


def detect_target_mismatch(
    *,
    requested_target: str,
    current_target: str | None,
    sim_dir: Path | None,
) -> bool:
    if current_target != requested_target:
        return True
    if sim_dir is None:
        return True
    try:
        resolved = sim_dir.resolve()
    except OSError:
        return True
    return resolved.name != requested_target


def validate_requested_target_artifacts(
    *,
    requested_target: str,
    current_target: str | None,
    sim_dir: Path | None,
) -> tuple[bool, str | None]:
    if detect_target_mismatch(
        requested_target=requested_target,
        current_target=current_target,
        sim_dir=sim_dir,
    ):
        return False, "target_mismatch"
    if sim_dir is None:
        return False, "target_dir_missing"
    if not (sim_dir / "sim_status.json").exists():
        return False, "sim_status_missing"
    movement_dir = sim_dir / "movement"
    movement_count = len(list(movement_dir.glob("*.json"))) if movement_dir.exists() else 0
    if movement_count <= 0:
        return False, "movement_missing"
    return True, None


def build_smoke_summary(
    *,
    attempt_id: int,
    status: str,
    target: str,
    commands: list[str],
    missing_fields: list[str] | None = None,
    error: str | None = None,
    failure_stage: str | None = None,
) -> dict[str, Any]:
    return {
        "attempt_id": int(attempt_id),
        "status": status,
        "target": target,
        "missing_fields": list(missing_fields or []),
        "commands": list(commands),
        "error": error,
        "failure_stage": failure_stage,
    }


def _http_request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def _kill_port_listeners(port: int) -> list[int]:
    import psutil

    killed: list[int] = []
    seen: set[int] = set()
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and getattr(conn.laddr, "port", None) == port and conn.pid and conn.pid not in seen:
            seen.add(conn.pid)
            try:
                proc = psutil.Process(conn.pid)
                proc.kill()
                killed.append(conn.pid)
            except (psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
                continue
            except psutil.AccessDenied:
                if os.name == "nt":
                    try:
                        completed = subprocess.run(
                            ["taskkill", "/PID", str(conn.pid), "/T", "/F"],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=10,
                        )
                        if completed.returncode == 0:
                            killed.append(conn.pid)
                    except Exception:
                        pass
    return killed


def _kill_backend_processes() -> list[int]:
    import psutil

    killed: list[int] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            name = str(proc.info.get("name") or "").lower()
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        if "python" not in name or "reverie.py" not in cmdline:
            continue
        try:
            proc.kill()
            killed.append(int(proc.info["pid"]))
        except (psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
            continue
        except psutil.AccessDenied:
            if os.name == "nt":
                try:
                    completed = subprocess.run(
                        ["taskkill", "/PID", str(proc.info["pid"]), "/T", "/F"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=10,
                    )
                    if completed.returncode == 0:
                        killed.append(int(proc.info["pid"]))
                except Exception:
                    pass
    return killed


def _wait_for_no_backend_processes(timeout_seconds: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        if not _kill_backend_processes():
            import psutil

            alive = []
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = str(proc.info.get("name") or "").lower()
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                if "python" in name and "reverie.py" in cmdline:
                    alive.append(proc.info["pid"])
            if not alive:
                return True
        time.sleep(1)
    return False


def _clean_temp_state() -> None:
    commands_dir = TEMP_ROOT / "commands"
    if commands_dir.exists():
        for cmd_file in commands_dir.glob("cmd_*.json"):
            try:
                cmd_file.unlink()
            except OSError:
                pass
    for name in ("curr_step.json", "curr_sim_code.json", "sim_output.json", "bridge_requests.jsonl"):
        try:
            (TEMP_ROOT / name).unlink()
        except OSError:
            pass


def _remove_target_dir(target: str) -> None:
    if not target or target == "curr_sim":
        return
    target_dir = STORAGE_ROOT / target
    if target_dir.exists():
        shutil.rmtree(target_dir)


def _read_curr_sim_code_pointer() -> str | None:
    path = TEMP_ROOT / "curr_sim_code.json"
    payload = _read_json(path, default={}) or {}
    sim_code = payload.get("sim_code")
    if isinstance(sim_code, str) and sim_code.strip():
        return sim_code.strip()
    return None


def _start_django(port: int) -> subprocess.Popen:
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUNTIME_LOG_DIR / f"week13_smoke_django_{port}.log"
    env = os.environ.copy()
    env.setdefault("EDSIM_MODE", "auto")
    env.setdefault("LLM_MODE", "local_only")
    env.setdefault("EMBEDDING_MODE", "local_only")
    env.setdefault("ENABLE_LLM_AGENTS", "0")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    handle = open(log_path, "w", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{int(port)}", "--noreload"],
        cwd=str(FRONTEND_ROOT),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )


def _wait_for_frontend(port: int, timeout_seconds: int) -> bool:
    url = f"http://127.0.0.1:{int(port)}/start_simulation?ui_mode=auto"
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            status, _ = _http_request_json("GET", url, None, timeout=3.0)
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _save_simulation_settings(port: int, seed: int, overrides: dict[str, Any] | None = None) -> tuple[int, Any]:
    payload = {
        "arrival_profile_mode": "normal",
        "doctor_starting_amount": 2,
        "triage_starting_amount": 1,
        "bedside_starting_amount": 1,
        "preload_waiting_room_patients": 0,
        "fill_injuries": 0.3,
        "add_patient_threshold": 0,
        "seed": int(seed),
    }
    if overrides:
        payload.update(overrides)
    return _http_request_json(
        "POST",
        f"http://127.0.0.1:{int(port)}/save_simulation_settings/",
        payload,
        timeout=10.0,
    )


def _start_backend(port: int, origin: str, target: str, headless: bool) -> tuple[int, Any]:
    query = "?headless=1" if headless else ""
    return _http_request_json(
        "POST",
        f"http://127.0.0.1:{int(port)}/start_backend/{origin}/{target}/{query}",
        {},
        timeout=120.0,
    )


def _send_run_command(port: int, run_steps: int) -> tuple[int, Any]:
    return _http_request_json(
        "POST",
        f"http://127.0.0.1:{int(port)}/send_sim_command/",
        build_run_command_payload(run_steps),
        timeout=10.0,
    )


def _force_shutdown_pid(port: int, pid: int) -> tuple[int, Any]:
    return _http_request_json(
        "POST",
        f"http://127.0.0.1:{int(port)}/force_shutdown/",
        {"pid": int(pid)},
        timeout=10.0,
    )


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _wait_for_run_completion(port: int, target: str, run_steps: int, timeout_seconds: int) -> tuple[bool, dict[str, Any]]:
    sim_dir = STORAGE_ROOT / target
    movement_dir = sim_dir / "movement"
    sim_status_path = sim_dir / "sim_status.json"
    output_url = f"http://127.0.0.1:{int(port)}/get_sim_output/"
    start = time.time()
    last_output = {}
    while time.time() - start < timeout_seconds:
        status, payload = _http_request_json("GET", output_url, None, timeout=5.0)
        if status == 200 and isinstance(payload, dict):
            last_output = payload
            outputs = payload.get("outputs", [])
            if outputs:
                latest = str(outputs[-1].get("output", ""))
                if f"Ran {int(run_steps)} steps." in latest:
                    movement_count = len(list(movement_dir.glob("*.json"))) if movement_dir.exists() else 0
                    if sim_status_path.exists() and movement_count > 0:
                        return True, last_output
        if sim_status_path.exists():
            try:
                status_payload = _read_json(sim_status_path, default={}) or {}
                step_value = status_payload.get("step")
                movement_count = len(list(movement_dir.glob("*.json"))) if movement_dir.exists() else 0
                if isinstance(step_value, int) and step_value >= int(run_steps) - 1 and movement_count >= int(run_steps):
                    if not isinstance(last_output, dict):
                        last_output = {}
                    last_output["completion_source"] = "sim_status_and_movement"
                    last_output["sim_status_step"] = step_value
                    last_output["movement_count"] = movement_count
                    return True, last_output
            except Exception:
                pass
        time.sleep(1)
    return False, last_output


def _wait_for_target_binding(target: str, timeout_seconds: int = 20) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        if _read_curr_sim_code_pointer() == target:
            return True
        time.sleep(0.5)
    return False


def _movement_payload_to_environment(sim_code: str, step: int, movement_payload: dict[str, Any]) -> dict[str, Any]:
    environment: dict[str, Any] = {}
    personas = movement_payload.get("persona", {})
    for persona_name, persona_payload in personas.items():
        movement = persona_payload.get("movement")
        if not isinstance(movement, list) or len(movement) < 2:
            continue
        try:
            pos_x = int(movement[0])
            pos_y = int(movement[1])
        except (TypeError, ValueError):
            continue
        role_value = persona_payload.get("role_key") or persona_payload.get("role") or "unknown"
        environment[persona_name] = {
            "maze": "Emergency Department",
            "x": pos_x,
            "y": pos_y,
            "name": persona_name,
            "role": role_value,
            "persona_role": role_value,
            "act": "idle",
        }
    return {"step": int(step), "sim_code": sim_code, "environment": environment}


def _replay_environment_bridge(port: int, target: str) -> dict[str, Any]:
    sim_dir = STORAGE_ROOT / target
    movement_dir = sim_dir / "movement"
    movement_steps = sorted(
        int(path.stem)
        for path in movement_dir.glob("*.json")
        if path.stem.isdigit()
    )
    processed = 0
    for step in movement_steps:
        status, movement_payload = _http_request_json(
            "POST",
            f"http://127.0.0.1:{int(port)}/update_environment/",
            {"step": step, "sim_code": target},
            timeout=10.0,
        )
        if status != 200 or not isinstance(movement_payload, dict) or movement_payload.get("<step>") != step:
            continue
        env_payload = _movement_payload_to_environment(target, step, movement_payload)
        process_status, process_payload = _http_request_json(
            "POST",
            f"http://127.0.0.1:{int(port)}/process_environment/",
            env_payload,
            timeout=10.0,
        )
        if process_status == 200 and isinstance(process_payload, dict) and process_payload.get("ok"):
            processed += 1
    return {
        "movement_steps": movement_steps,
        "processed_steps": processed,
    }


def _load_failure_report_for_target(target: str) -> dict[str, Any]:
    sim_dir = STORAGE_ROOT / target
    return write_failure_report(sim_dir)


def _run_verify(sim_code: str, strict: bool) -> subprocess.CompletedProcess:
    args = [sys.executable, "scripts/verify_step_contract.py", "--sim-code", sim_code]
    if strict:
        args.append("--strict-week13-failure-metrics")
        args.append("--week13-failure-metrics-only")
    return subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _system_health_summary(status_payload: dict[str, Any]) -> dict[str, Any]:
    system_health = status_payload.get("system_health", {}) if isinstance(status_payload, dict) else {}
    return {
        "failed": system_health.get("failed"),
        "failed_reason": system_health.get("failed_reason"),
        "failure_rate": system_health.get("failure_rate"),
        "failed_at_step": system_health.get("failed_at_step"),
    }


def _resource_field_summary(status_payload: dict[str, Any]) -> dict[str, Any]:
    resources = status_payload.get("resources", {}) if isinstance(status_payload, dict) else {}
    return {field: resources.get(field) for field in REQUIRED_RESOURCE_FIELDS}


def _write_debug_markdown(diag: dict[str, Any], attempts: list[dict[str, Any]], final_summary: dict[str, Any]) -> None:
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Week13 Runtime Smoke Debug")
    lines.append("")
    lines.append("## Diagnosis")
    lines.append("")
    for key, value in diag.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Attempts")
    lines.append("")
    for attempt in attempts:
        lines.append(f"### Attempt {attempt['attempt_id']}")
        lines.append("")
        lines.append(f"- changed_files: {attempt.get('changed_files', [])}")
        lines.append(f"- command_run: `{attempt.get('command_run', '')}`")
        lines.append(f"- failure_stage: {attempt.get('failure_stage')}")
        lines.append(f"- error_message: {attempt.get('error_message')}")
        lines.append(f"- hypothesis: {attempt.get('hypothesis')}")
        lines.append(f"- fix_applied: {attempt.get('fix_applied')}")
        lines.append(f"- result: {attempt.get('result')}")
        lines.append("")
    lines.append("## Final Summary")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(final_summary, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def _diagnosis_snapshot() -> dict[str, Any]:
    return {
        "why_git_bash_was_used": "Previous launcher reused start_auto_backend_edsim39.sh and bootstrap_auto_sim_edsim39.sh, both Bash entry points.",
        "signal_pipe_command": '& "C:\\Program Files\\Git\\bin\\bash.exe" .\\bootstrap_auto_sim_edsim39.sh 8010 ed_sim_n5 curr_sim 5',
        "powershell_native_path_exists": True,
        "python_native_path_exists": True,
        "django_frontend_command": f"{sys.executable} manage.py runserver 127.0.0.1:<port> --noreload",
        "backend_start_endpoint": "/start_backend/<origin>/<target>/",
        "run_command_injection": "/send_sim_command/ with JSON payload {\"command\": \"run 5\"}",
        "latest_trusted_sim_dir_rule": "Use a fresh target sim code and resolve storage/<target>; do not reuse curr_sim.",
        "old_curr_sim_pollution_exists": True,
        "failure_metrics_connected_in_reverie": True,
    }


def run_smoke(
    port: int,
    origin: str,
    target: str,
    run_steps: int,
    max_attempts: int,
    settings_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target == "curr_sim":
        raise SystemExit("Refusing target=curr_sim for smoke; use a fresh smoke target.")

    diag = _diagnosis_snapshot()
    attempts_doc: list[dict[str, Any]] = []
    configs = [
        AttemptConfig(1, "headless_postprocess_environment", True, True, 90),
        AttemptConfig(2, "headless_postprocess_environment_retry", True, True, 120),
        AttemptConfig(3, "non_headless_live_bridge_fallback", False, True, 120),
    ][: max(1, int(max_attempts))]
    adaptive_wait_seconds = max(
        90,
        min(
            21600,
            int(run_steps) * 15,
        ),
    )
    configs = [
        AttemptConfig(
            attempt_id=config.attempt_id,
            strategy=config.strategy,
            headless=config.headless,
            bootstrap_environment_from_movement=config.bootstrap_environment_from_movement,
            wait_seconds=max(config.wait_seconds, adaptive_wait_seconds),
        )
        for config in configs
    ]

    last_summary: dict[str, Any] = {}
    for config in configs:
        django_proc = None
        command_log = [
            f"{sys.executable} scripts/run_week13_smoke.py --port {port} --origin {origin} --target {target} --run-steps {run_steps} --max-attempts {max_attempts}"
        ]
        attempt_record = {
            "attempt_id": config.attempt_id,
            "changed_files": [
                "scripts/run_week13_smoke.py",
                "scripts/run_week13_smoke.ps1",
                "tests/backend/test_week13_smoke_launcher.py",
                "docs/week13_runtime_smoke_debug.md",
            ],
            "command_run": command_log[0],
            "failure_stage": None,
            "error_message": None,
            "hypothesis": None,
            "fix_applied": None if config.attempt_id == 1 else "Retried with launcher strategy variant and fresh target cleanup.",
            "result": None,
        }
        target_attempt = f"{target}_a{config.attempt_id}"
        try:
            _kill_port_listeners(port)
            _kill_backend_processes()
            no_backend = _wait_for_no_backend_processes(timeout_seconds=15)
            if not no_backend:
                attempt_record["failure_stage"] = "backend_cleanup"
                attempt_record["error_message"] = "Existing reverie.py process could not be terminated."
                attempt_record["hypothesis"] = "Old backend process is still alive and would hijack command routing."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue
            _clean_temp_state()
            _remove_target_dir(target_attempt)

            django_proc = _start_django(port)
            frontend_ready = _wait_for_frontend(port, timeout_seconds=30)
            if not frontend_ready:
                attempt_record["failure_stage"] = "frontend_start"
                attempt_record["error_message"] = "Frontend failed readiness probe."
                attempt_record["hypothesis"] = "Django runserver did not start or wrong port binding."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            status, payload = _save_simulation_settings(
                port,
                seed=20260603 + config.attempt_id,
                overrides=settings_overrides,
            )
            if status != 200 or not isinstance(payload, dict) or not payload.get("ok"):
                attempt_record["failure_stage"] = "save_settings"
                attempt_record["error_message"] = str(payload)
                attempt_record["hypothesis"] = "save_simulation_settings rejected payload."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            status, payload = _start_backend(port, origin, target_attempt, headless=config.headless)
            if status != 200 or not isinstance(payload, dict) or payload.get("ok") in (False, None):
                if isinstance(payload, dict) and payload.get("error") == "stale_backend_target_mismatch":
                    attempt_record["failure_stage"] = "start_backend"
                    attempt_record["error_message"] = (
                        f"stale_backend_target_mismatch: running_target={payload.get('running_target')!r}, "
                        f"requested_target={payload.get('requested_target')!r}, "
                        f"running_pids={payload.get('running_pids')!r}, "
                        f"shutdown_result={payload.get('shutdown_result')!r}"
                    )
                    attempt_record["hypothesis"] = "Backend lifecycle rejected stale target reuse but shutdown did not succeed."
                    attempt_record["result"] = "failed"
                    attempts_doc.append(attempt_record)
                    last_summary = build_smoke_summary(
                        attempt_id=config.attempt_id,
                        status="failed",
                        target=target_attempt,
                        commands=command_log,
                        error=attempt_record["error_message"],
                        failure_stage=attempt_record["failure_stage"],
                    )
                    continue
                attempt_record["failure_stage"] = "start_backend"
                attempt_record["error_message"] = str(payload)
                attempt_record["hypothesis"] = "Backend launcher or reverie process failed startup health check."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            target_bound = _wait_for_target_binding(target_attempt, timeout_seconds=20)
            if not target_bound:
                reused_pids = []
                if isinstance(payload, dict):
                    reused_pids = [int(pid) for pid in payload.get("running_pids", []) if str(pid).isdigit()]
                shutdown_results = []
                for pid in reused_pids:
                    shutdown_results.append({"pid": pid, "response": _force_shutdown_pid(port, pid)})
                attempt_record["failure_stage"] = "target_binding"
                attempt_record["error_message"] = (
                    f"curr_sim_code.json did not switch to {target_attempt}; "
                    f"current={_read_curr_sim_code_pointer()!r}; start_backend_response={payload}; "
                    f"force_shutdown_results={shutdown_results}"
                )
                attempt_record["hypothesis"] = "start_backend reused an existing backend instance instead of binding to the new target."
                if shutdown_results:
                    attempt_record["fix_applied"] = "Called /force_shutdown/ for reused backend pid(s) before next retry."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            status, payload = _send_run_command(port, run_steps)
            if status != 200 or not isinstance(payload, dict) or not payload.get("ok"):
                attempt_record["failure_stage"] = "send_command"
                attempt_record["error_message"] = str(payload)
                attempt_record["hypothesis"] = "Command endpoint rejected run payload."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            completed, output_payload = _wait_for_run_completion(port, target_attempt, run_steps, config.wait_seconds)
            if not completed:
                attempt_record["failure_stage"] = "run_completion"
                attempt_record["error_message"] = json.dumps(output_payload, ensure_ascii=False)
                attempt_record["hypothesis"] = "Backend did not finish run or movement/sim_status files were not written."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            bridge_summary = {"movement_steps": [], "processed_steps": 0}
            if config.bootstrap_environment_from_movement:
                bridge_summary = _replay_environment_bridge(port, target_attempt)

            sim_dir = resolve_target_sim_dir(STORAGE_ROOT, target_attempt)
            current_target = _read_curr_sim_code_pointer()
            valid_artifacts, artifact_error = validate_requested_target_artifacts(
                requested_target=target_attempt,
                current_target=current_target,
                sim_dir=sim_dir,
            )
            sim_status_path = sim_dir / "sim_status.json"
            if not valid_artifacts:
                attempt_record["failure_stage"] = artifact_error
                attempt_record["error_message"] = (
                    f"requested_target={target_attempt!r}, current_target={current_target!r}, "
                    f"sim_dir={str(sim_dir)!r}, artifact_error={artifact_error!r}"
                )
                attempt_record["hypothesis"] = "Run output belonged to a stale target or required files were written under the wrong sim."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            status_payload = _read_json(sim_status_path, default={}) or {}
            missing_fields = find_missing_failure_fields(status_payload)
            if missing_fields:
                attempt_record["failure_stage"] = "failure_metrics_schema"
                attempt_record["error_message"] = ", ".join(missing_fields)
                attempt_record["hypothesis"] = "Failure metrics merge into sim_status is incomplete."
                attempt_record["result"] = "failed"
                attempts_doc.append(attempt_record)
                last_summary = build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="failed",
                    target=target_attempt,
                    commands=command_log,
                    missing_fields=missing_fields,
                    error=attempt_record["error_message"],
                    failure_stage=attempt_record["failure_stage"],
                )
                continue

            report = _load_failure_report_for_target(target_attempt)
            report_path = sim_dir / "analysis" / "failure_report.json"
            verify_normal = _run_verify(target_attempt, strict=False)
            verify_strict = _run_verify(target_attempt, strict=True)

            movement_count = len(list((sim_dir / "movement").glob("*.json")))
            env_count = len(list((sim_dir / "environment").glob("*.json"))) if (sim_dir / "environment").exists() else 0
            attempt_record["result"] = "success"
            attempts_doc.append(attempt_record)
            last_summary = {
                **build_smoke_summary(
                    attempt_id=config.attempt_id,
                    status="success",
                    target=target_attempt,
                    commands=command_log,
                ),
                "frontend_ready": True,
                "backend_started": True,
                "command_sent": True,
                "movement_generated": movement_count > 0,
                "sim_status_generated": True,
                "failure_metrics_present": True,
                "strict_verify_passed": verify_strict.returncode == 0,
                "target": target_attempt,
                "sim_dir": str(sim_dir),
                "movement_files_count": movement_count,
                "environment_files_count": env_count,
                "bridge_summary": bridge_summary,
                "sim_status_path": str(sim_status_path),
                "resource_summary": _resource_field_summary(status_payload),
                "system_health_summary": _system_health_summary(status_payload),
                "failure_report_path": str(report_path),
                "failure_report_summary": {
                    "arrivals_total": report.get("arrivals_total"),
                    "failed_patients_count": report.get("failed_patients_count"),
                    "failure_rate": report.get("failure_rate"),
                    "system_failed": report.get("system_failed"),
                    "failure_reason_counts": report.get("failure_reason_counts"),
                    "patient_level_detail_available": report.get("patient_level_detail_available"),
                },
                "verify_normal": {
                    "returncode": verify_normal.returncode,
                    "stdout": verify_normal.stdout,
                    "stderr": verify_normal.stderr,
                },
                "verify_strict": {
                    "returncode": verify_strict.returncode,
                    "stdout": verify_strict.stdout,
                    "stderr": verify_strict.stderr,
                },
            }
            _write_debug_markdown(diag, attempts_doc, last_summary)
            return last_summary
        finally:
            if django_proc is not None:
                try:
                    django_proc.kill()
                except Exception:
                    pass
            _kill_backend_processes()

    _write_debug_markdown(diag, attempts_doc, last_summary)
    return last_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a PowerShell/Python-native Week13 smoke validation.")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--origin", default="ed_sim_n5")
    parser.add_argument("--target", default="week13_smoke_test")
    parser.add_argument("--run-steps", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_smoke(
        port=int(args.port),
        origin=str(args.origin),
        target=str(args.target),
        run_steps=int(args.run_steps),
        max_attempts=int(args.max_attempts),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if summary.get("status") != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
