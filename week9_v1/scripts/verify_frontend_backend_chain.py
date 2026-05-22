from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "environment" / "frontend_server"
TEMP_DIR = FRONTEND_DIR / "temp_storage"
LOG_DIR = FRONTEND_DIR / "logs"
STORAGE_DIR = FRONTEND_DIR / "storage"
TARGET_SIM_DIR = STORAGE_DIR / "curr_sim"
SEED_SIM_DIR = STORAGE_DIR / "ed_sim_n5"
PYTHON = Path(r"D:\anaconda3\envs\edmas\python.exe")
BASE_URL = "http://127.0.0.1:8010"
SESSION = requests.Session()
SESSION.trust_env = False

DEBUG_REPORT_PATH = TEMP_DIR / "debug_final_report.json"
STATUS_SNAPSHOT_PATH = TEMP_DIR / "api_status_snapshot.json"
STABILITY_LOG_PATH = TEMP_DIR / "stability_proof.log"
CRASH_LOG_PATH = LOG_DIR / "crash.log"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def _tail_file(path: Path, max_lines: int = 80) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    return "\n".join(lines[-max_lines:])


def _ps(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _kill_reverie_processes() -> List[int]:
    query = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'reverie.py' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    result = _ps(query)
    pids: List[int] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    if pids:
        stop = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'reverie.py' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        _ps(stop)
    return pids


def _kill_django_processes() -> List[int]:
    query = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'manage.py\\s+runserver\\s+127\\.0\\.0\\.1:8010' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    result = _ps(query)
    pids: List[int] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    if pids:
        stop = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'manage.py\\s+runserver\\s+127\\.0\\.0\\.1:8010' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        _ps(stop)
    return pids


def _seed_integrity() -> Dict[str, Any]:
    required = ["movement", "environment", "personas", "reverie"]
    return {
        "path": str(SEED_SIM_DIR),
        "exists": SEED_SIM_DIR.exists(),
        "required_dirs": {name: (SEED_SIM_DIR / name).exists() for name in required},
    }


def _count_json_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob("*.json")))


def _latest_step(directory: Path) -> Optional[int]:
    steps: List[int] = []
    if not directory.exists():
        return None
    for path in directory.glob("*.json"):
        try:
            steps.append(int(path.stem))
        except ValueError:
            continue
    return max(steps) if steps else None


def _physical_runtime_state() -> Dict[str, Any]:
    movement_dir = TARGET_SIM_DIR / "movement"
    environment_dir = TARGET_SIM_DIR / "environment"
    return {
        "movement_file_count": _count_json_files(movement_dir),
        "environment_file_count": _count_json_files(environment_dir),
        "latest_movement_file_step": _latest_step(movement_dir),
        "latest_environment_file_step": _latest_step(environment_dir),
        "movement_10_exists": (movement_dir / "10.json").exists(),
        "environment_10_exists": (environment_dir / "10.json").exists(),
        "sim_status_exists": (TARGET_SIM_DIR / "sim_status.json").exists(),
    }


def _get_dashboard() -> Dict[str, Any]:
    try:
        resp = SESSION.get(f"{BASE_URL}/api/live_dashboard/", timeout=5)
        return {"http": resp.status_code, "payload": _safe_json(resp)}
    except Exception as exc:
        return {"http": None, "payload": {"error": str(exc)}}


def _state_snapshot(label: str) -> Dict[str, Any]:
    curr_step_payload = _read_json(TEMP_DIR / "curr_step.json", default={})
    curr_sim_payload = _read_json(TEMP_DIR / "curr_sim_code.json", default={})
    dashboard = _get_dashboard()
    payload = dashboard.get("payload") or {}
    runtime_sync = payload.get("runtime_sync") or {}
    backend_health = payload.get("backend_health") or {}
    commands = sorted((TEMP_DIR / "commands").glob("cmd_*.json")) if (TEMP_DIR / "commands").exists() else []
    snapshot = {
        "label": label,
        "timestamp": _timestamp(),
        "curr_step_exists": (TEMP_DIR / "curr_step.json").exists(),
        "curr_step": curr_step_payload.get("step"),
        "curr_sim_code_exists": (TEMP_DIR / "curr_sim_code.json").exists(),
        "curr_sim_code": curr_sim_payload.get("sim_code"),
        "pending_command_count": len(commands),
        "pending_command_files": [path.name for path in commands],
        "latest_movement_step": runtime_sync.get("latest_movement_step"),
        "latest_environment_step": runtime_sync.get("latest_environment_step"),
        "backend_alive": backend_health.get("backend_alive"),
        "stalled": backend_health.get("stalled"),
        "dashboard_http": dashboard.get("http"),
    }
    return snapshot


def _clean_runtime_state(*, kill_django: bool = False) -> Dict[str, Any]:
    pre = _state_snapshot("pre_cleanup")
    killed_reverie = _kill_reverie_processes()
    killed_django = _kill_django_processes() if kill_django else []

    removed_files: List[str] = []
    for temp_name in ("curr_step.json", "curr_sim_code.json", "sim_output.json"):
        path = TEMP_DIR / temp_name
        if path.exists():
            path.unlink(missing_ok=True)
            removed_files.append(str(path))

    cmd_dir = TEMP_DIR / "commands"
    removed_commands: List[str] = []
    if cmd_dir.exists():
        for cmd_file in cmd_dir.glob("cmd_*.json"):
            removed_commands.append(cmd_file.name)
            cmd_file.unlink(missing_ok=True)
        try:
            shutil.rmtree(cmd_dir)
        except FileNotFoundError:
            pass

    removed_runtime_files: List[str] = []
    for subdir_name in ("movement", "environment"):
        subdir = TARGET_SIM_DIR / subdir_name
        if not subdir.exists():
            continue
        for json_file in subdir.glob("*.json"):
            removed_runtime_files.append(str(json_file))
            json_file.unlink(missing_ok=True)
    for runtime_name in ("sim_status.json", "sim_status.txt"):
        runtime_path = TARGET_SIM_DIR / runtime_name
        if runtime_path.exists():
            removed_runtime_files.append(str(runtime_path))
            runtime_path.unlink(missing_ok=True)

    return {
        "pre_cleanup": pre,
        "killed_reverie_pids": killed_reverie,
        "killed_django_pids": killed_django,
        "removed_temp_files": removed_files,
        "removed_command_files": removed_commands,
        "removed_runtime_files": removed_runtime_files,
        "post_cleanup": _state_snapshot("post_cleanup"),
    }


def _start_django() -> subprocess.Popen:
    env = os.environ.copy()
    env["ENABLE_LLM_AGENTS"] = "0"
    env["EDSIM_MODE"] = "auto"
    env["LLM_MODE"] = "local_only"
    env["EMBEDDING_MODE"] = "local_only"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    django_log = open(LOG_DIR / "django_runtime.log", "w", encoding="utf-8")
    return subprocess.Popen(
        [str(PYTHON), "manage.py", "runserver", "127.0.0.1:8010", "--noreload"],
        cwd=str(FRONTEND_DIR),
        env=env,
        stdout=django_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )


def _wait_http_ready(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_error: Optional[str] = None
    while time.time() < deadline:
        try:
            response = SESSION.get(f"{BASE_URL}/start_simulation?ui_mode=auto", timeout=2)
            if response.status_code == 200:
                return
            last_error = f"http {response.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Django server not ready in {timeout}s: {last_error}")


def _start_backend_with_retries(max_attempts: int = 2) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        response = SESSION.post(f"{BASE_URL}/start_backend/ed_sim_n5/curr_sim/?headless=1", timeout=60)
        payload = _safe_json(response)
        attempts.append({
            "attempt": attempt,
            "http": response.status_code,
            "payload": payload,
            "snapshot": _state_snapshot(f"post_start_attempt_{attempt}"),
            "crash_log_tail": _tail_file(CRASH_LOG_PATH, max_lines=80),
        })
        if response.status_code == 200 and payload.get("ok"):
            return {"ok": True, "attempts": attempts, "payload": payload}
        if response.status_code == 503:
            _clean_runtime_state(kill_django=False)
            time.sleep(1.0)
            continue
        break
    return {"ok": False, "attempts": attempts, "payload": attempts[-1]["payload"] if attempts else {}}


def _send_command(command: str) -> Dict[str, Any]:
    response = SESSION.post(f"{BASE_URL}/send_sim_command/", json={"command": command}, timeout=20)
    payload = _safe_json(response)
    return {"http": response.status_code, "payload": payload}


def _wait_for_command_output(command: str, timeout: float = 180.0) -> Dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = SESSION.get(f"{BASE_URL}/get_sim_output/", timeout=5)
        payload = _safe_json(response)
        for item in reversed(payload.get("outputs", [])):
            if str(item.get("command", "")).strip() == command:
                return item
        time.sleep(1.0)
    raise RuntimeError(f"Timed out waiting for command output: {command}")


def _monitor_movement_growth(
    *,
    target_movement_step: int,
    interval_seconds: float = 5.0,
    timeout: float = 180.0,
) -> Dict[str, Any]:
    deadline = time.time() + timeout
    samples: List[Dict[str, Any]] = []
    while time.time() < deadline:
        dashboard = _get_dashboard()
        payload = dashboard.get("payload") or {}
        runtime_sync = payload.get("runtime_sync") or {}
        backend_health = payload.get("backend_health") or {}
        sim_status_step = payload.get("step")
        latest_movement_step = runtime_sync.get("latest_movement_step")
        latest_environment_step = runtime_sync.get("latest_environment_step")
        sample = {
            "timestamp": _timestamp(),
            "movement_file_count": _count_json_files(TARGET_SIM_DIR / "movement"),
            "environment_file_count": _count_json_files(TARGET_SIM_DIR / "environment"),
            "latest_movement_step": latest_movement_step,
            "curr_step_pointer": runtime_sync.get("curr_step_pointer"),
            "latest_environment_step": latest_environment_step,
            "sim_status_step": sim_status_step,
            "backend_alive": backend_health.get("backend_alive"),
            "stalled": backend_health.get("stalled"),
            "movement_10_exists": (TARGET_SIM_DIR / "movement" / "10.json").exists(),
            "environment_10_exists": (TARGET_SIM_DIR / "environment" / "10.json").exists(),
        }
        samples.append(sample)
        _append_line(STABILITY_LOG_PATH, json.dumps(sample, ensure_ascii=False))
        if (
            isinstance(latest_movement_step, int)
            and latest_movement_step >= target_movement_step
            and backend_health.get("backend_alive") is True
            and backend_health.get("stalled") is False
        ):
            return {"ok": True, "samples": samples, "target_movement_step": target_movement_step}
        time.sleep(interval_seconds)
    return {"ok": False, "samples": samples, "target_movement_step": target_movement_step}


def _run_bridge_sync(max_steps: int = 10) -> Dict[str, Any]:
    result = subprocess.run(
        [str(PYTHON), str(ROOT / "scripts" / "debug_bridge_sync.py"), "--max-steps", str(max_steps), "--max-polls", "20"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _assert_physical_acceptance() -> Dict[str, Any]:
    dashboard = _get_dashboard().get("payload") or {}
    runtime_sync = dashboard.get("runtime_sync") or {}
    backend_health = dashboard.get("backend_health") or {}
    physical = _physical_runtime_state()
    acceptance = {
        "dashboard_step": dashboard.get("step"),
        "latest_movement_step": runtime_sync.get("latest_movement_step"),
        "latest_environment_step": runtime_sync.get("latest_environment_step"),
        "backend_alive": backend_health.get("backend_alive"),
        "stalled": backend_health.get("stalled"),
        **physical,
    }
    if not (
        backend_health.get("backend_alive") is True
        and backend_health.get("stalled") is False
        and isinstance(runtime_sync.get("latest_movement_step"), int)
        and runtime_sync.get("latest_movement_step") >= 10
        and isinstance(runtime_sync.get("latest_environment_step"), int)
        and runtime_sync.get("latest_environment_step") >= 10
        and physical["movement_10_exists"]
        and physical["environment_10_exists"]
    ):
        raise RuntimeError(f"Physical acceptance failed: {json.dumps(acceptance, ensure_ascii=False)}")
    return acceptance


def _ensure_minimum_runtime_step(min_step: int = 10) -> Dict[str, Any]:
    dashboard = _get_dashboard().get("payload") or {}
    runtime_sync = dashboard.get("runtime_sync") or {}
    latest_movement_step = runtime_sync.get("latest_movement_step")
    try:
        latest_movement_step = int(latest_movement_step) if latest_movement_step is not None else None
    except Exception:
        latest_movement_step = None
    if latest_movement_step is not None and latest_movement_step >= min_step:
        return {
            "already_satisfied": True,
            "latest_movement_step": latest_movement_step,
            "physical_state": _physical_runtime_state(),
        }

    next_command = "run 1"
    send_result = _send_command(next_command)
    if send_result["http"] != 200 or not send_result["payload"].get("ok"):
        raise RuntimeError(f"Failed to send {next_command}: {json.dumps(send_result, ensure_ascii=False)}")
    output_item = _wait_for_command_output(next_command)
    if "Ran " not in str(output_item.get("output", "")):
        raise RuntimeError(f"Follow-up {next_command} did not complete cleanly: {json.dumps(output_item, ensure_ascii=False)}")
    growth = _monitor_movement_growth(target_movement_step=min_step, timeout=120.0)
    bridge = _run_bridge_sync(max_steps=10)
    return {
        "already_satisfied": False,
        "command": next_command,
        "send_command": send_result,
        "command_output": output_item,
        "growth_monitor": growth,
        "bridge_sync": bridge,
        "physical_state": _physical_runtime_state(),
    }


def _ensure_seed_integrity_or_raise() -> Dict[str, Any]:
    integrity = _seed_integrity()
    if not integrity["exists"] or not all(integrity["required_dirs"].values()):
        raise RuntimeError(f"Seed simulation storage is incomplete: {integrity}")
    return integrity


def _run_iteration(iteration_index: int, command: str, *, restart_backend: bool) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "iteration": iteration_index,
        "command": command,
        "restart_backend": restart_backend,
        "issues_found": [],
        "fixes_applied": [],
        "state_snapshot_before": _state_snapshot(f"iteration_{iteration_index}_before"),
    }

    if restart_backend:
        cleanup_info = _clean_runtime_state(kill_django=False)
        entry["cleanup"] = cleanup_info
        entry["fixes_applied"].append("cleared stale temp_storage runtime pointers and pending commands")
        backend_start = _start_backend_with_retries()
        entry["start_backend"] = backend_start
        if not backend_start.get("ok"):
            entry["issues_found"].append("backend failed health check after startup")
            raise RuntimeError(json.dumps(entry, ensure_ascii=False, indent=2))
        entry["fixes_applied"].append("restarted reverie in headless local-only mode")

    pre_dashboard = _get_dashboard().get("payload") or {}
    baseline_runtime = pre_dashboard.get("runtime_sync") or {}
    baseline_latest_movement = baseline_runtime.get("latest_movement_step")
    baseline_pointer = baseline_runtime.get("curr_step_pointer")
    try:
        baseline_latest_movement = int(baseline_latest_movement) if baseline_latest_movement is not None else None
    except Exception:
        baseline_latest_movement = None
    try:
        baseline_pointer = int(baseline_pointer) if baseline_pointer is not None else None
    except Exception:
        baseline_pointer = None
    entry["baseline_runtime_sync"] = baseline_runtime

    send_result = _send_command(command)
    entry["send_command"] = send_result
    if send_result["http"] != 200 or not send_result["payload"].get("ok"):
        entry["issues_found"].append("send_sim_command failed")
        raise RuntimeError(json.dumps(entry, ensure_ascii=False, indent=2))

    output_item = _wait_for_command_output(command)
    entry["command_output"] = output_item
    if "Ran " not in str(output_item.get("output", "")):
        entry["issues_found"].append("command loop did not report successful completion")
        raise RuntimeError(json.dumps(entry, ensure_ascii=False, indent=2))

    command_steps = int(command.split()[-1])
    target_movement_step = max(
        baseline_latest_movement if baseline_latest_movement is not None else -1,
        (baseline_pointer if baseline_pointer is not None else 0) + command_steps - 1,
    )
    growth = _monitor_movement_growth(target_movement_step=target_movement_step)
    entry["growth_monitor"] = growth
    if not growth.get("ok"):
        entry["issues_found"].append("movement files did not continue growing")
        entry["crash_log_tail"] = _tail_file(CRASH_LOG_PATH, max_lines=120)
        raise RuntimeError(json.dumps(entry, ensure_ascii=False, indent=2))
    entry["fixes_applied"].append("verified movement growth from filesystem and live dashboard")

    bridge_result = _run_bridge_sync(max_steps=10)
    entry["bridge_sync"] = bridge_result
    if bridge_result["returncode"] != 0:
        entry["issues_found"].append("bridge write-back lag or backend stall during simulated frontend sync")
        raise RuntimeError(json.dumps(entry, ensure_ascii=False, indent=2))
    entry["fixes_applied"].append("confirmed update/process bridge from backend perspective")

    entry["state_snapshot_after"] = _state_snapshot(f"iteration_{iteration_index}_after")
    entry["physical_state_after"] = _physical_runtime_state()
    return entry


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if STABILITY_LOG_PATH.exists():
        STABILITY_LOG_PATH.unlink()

    report: Dict[str, Any] = {
        "timestamp": _timestamp(),
        "mode": {
            "LLM_MODE": "local_only",
            "EMBEDDING_MODE": "local_only",
            "ENABLE_LLM_AGENTS": "0",
        },
        "seed_integrity": _ensure_seed_integrity_or_raise(),
        "iterations": [],
        "final_status": "running",
    }

    django_proc: Optional[subprocess.Popen] = None
    try:
        _kill_reverie_processes()
        _kill_django_processes()
        django_proc = _start_django()
        _wait_http_ready()

        report["iterations"].append(_run_iteration(1, "run 1", restart_backend=True))
        report["iterations"].append(_run_iteration(2, "run 10", restart_backend=False))
        report["iterations"].append(_run_iteration(3, "run 10", restart_backend=True))
        report["final_step_topoff"] = _ensure_minimum_runtime_step(10)

        final_dashboard = _get_dashboard().get("payload") or {}
        _write_json(STATUS_SNAPSHOT_PATH, final_dashboard)
        report["final_dashboard"] = final_dashboard
        report["physical_acceptance"] = _assert_physical_acceptance()
        report["final_status"] = "ok"
        report["crash_log_tail"] = _tail_file(CRASH_LOG_PATH, max_lines=120)
        _write_json(DEBUG_REPORT_PATH, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        final_dashboard = _get_dashboard().get("payload") or {}
        report["final_status"] = "failed"
        report["error"] = str(exc)
        report["final_dashboard"] = final_dashboard
        report["physical_acceptance"] = _physical_runtime_state()
        report["crash_log_tail"] = _tail_file(CRASH_LOG_PATH, max_lines=120)
        _write_json(STATUS_SNAPSHOT_PATH, final_dashboard)
        _write_json(DEBUG_REPORT_PATH, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    finally:
        if django_proc is not None:
            try:
                django_proc.terminate()
                django_proc.wait(timeout=10)
            except Exception:
                pass
        _kill_reverie_processes()
        _kill_django_processes()


if __name__ == "__main__":
    raise SystemExit(main())
