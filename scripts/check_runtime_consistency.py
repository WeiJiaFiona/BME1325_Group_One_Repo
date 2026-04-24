import argparse
import json
import sys
from pathlib import Path
from typing import Union


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = REPO_ROOT / "environment" / "frontend_server"
DEFAULT_STORAGE_ROOT = FRONTEND_ROOT / "storage"
DEFAULT_TEMP_ROOT = FRONTEND_ROOT / "temp_storage"


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def numeric_steps(path: Path) -> list[int]:
    if not path.exists():
        return []
    steps = []
    for file_path in path.glob("*.json"):
        try:
            steps.append(int(file_path.stem))
        except ValueError:
            continue
    return sorted(steps)


def missing_ranges(steps: list[int], start: int, end: int, limit: int = 20) -> list[int]:
    present = set(steps)
    missing = [step for step in range(start, end + 1) if step not in present]
    return missing[:limit]


def build_report(
    *,
    sim_code: str,
    storage_root: Path,
    temp_root: Path,
    mode: str,
    allowed_status_lag: int,
    allowed_curr_step_lag: int,
):
    sim_dir = storage_root / sim_code
    status = read_json(sim_dir / "sim_status.json", default={}) or {}
    curr_step_payload = read_json(temp_root / "curr_step.json", default={}) or {}
    curr_sim_payload = read_json(temp_root / "curr_sim_code.json", default={}) or {}

    movement_steps = numeric_steps(sim_dir / "movement")
    environment_steps = numeric_steps(sim_dir / "environment")

    status_step = status.get("step")
    curr_step = curr_step_payload.get("step")
    try:
        status_step = int(status_step)
    except (TypeError, ValueError):
        status_step = None
    try:
        curr_step = int(curr_step)
    except (TypeError, ValueError):
        curr_step = None

    latest_movement = movement_steps[-1] if movement_steps else None
    latest_environment = environment_steps[-1] if environment_steps else None
    expected_latest_from_curr = curr_step - 1 if curr_step is not None else None

    checks = []

    def add_check(name: str, passed: bool, detail: Union[dict, str]):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    add_check("sim_dir_exists", sim_dir.exists(), str(sim_dir))
    add_check("curr_sim_points_to_sim_code", curr_sim_payload.get("sim_code") == sim_code, curr_sim_payload)
    add_check("status_step_present", status_step is not None, {"status_step": status_step})
    add_check("curr_step_present", curr_step is not None, {"curr_step": curr_step})
    add_check("movement_files_present", bool(movement_steps), {"count": len(movement_steps)})
    add_check("environment_files_present", bool(environment_steps), {"count": len(environment_steps)})

    if curr_step is not None and latest_movement is not None:
        add_check(
            "movement_reaches_curr_step_window",
            abs(expected_latest_from_curr - latest_movement) <= allowed_curr_step_lag,
            {
                "curr_step": curr_step,
                "expected_latest_movement": expected_latest_from_curr,
                "latest_movement": latest_movement,
                "allowed_curr_step_lag": allowed_curr_step_lag,
            },
        )

    if status_step is not None and latest_movement is not None:
        add_check(
            "status_close_to_latest_movement",
            0 <= latest_movement - status_step <= allowed_status_lag,
            {
                "status_step": status_step,
                "latest_movement": latest_movement,
                "actual_lag": latest_movement - status_step,
                "allowed_status_lag": allowed_status_lag,
            },
        )

    if movement_steps:
        movement_start = movement_steps[0]
        movement_end = movement_steps[-1]
        add_check(
            "movement_steps_contiguous",
            not missing_ranges(movement_steps, movement_start, movement_end),
            {
                "start": movement_start,
                "end": movement_end,
                "count": len(movement_steps),
                "missing_first_values": missing_ranges(movement_steps, movement_start, movement_end),
            },
        )

    if mode == "ui":
        if curr_step is not None and latest_environment is not None:
            add_check(
                "environment_reaches_curr_step_window",
                abs(curr_step - latest_environment) <= allowed_curr_step_lag,
                {
                    "curr_step": curr_step,
                    "latest_environment": latest_environment,
                    "allowed_curr_step_lag": allowed_curr_step_lag,
                },
            )
        if environment_steps:
            env_start = environment_steps[0]
            env_end = environment_steps[-1]
            add_check(
                "environment_steps_contiguous",
                not missing_ranges(environment_steps, env_start, env_end),
                {
                    "start": env_start,
                    "end": env_end,
                    "count": len(environment_steps),
                    "missing_first_values": missing_ranges(environment_steps, env_start, env_end),
                },
            )
    else:
        add_check(
            "environment_ui_feedback_not_required_in_headless",
            True,
            "headless mode builds environment in backend; UI feedback continuity is not asserted",
        )

    passed = all(check["passed"] for check in checks)
    return {
        "passed": passed,
        "mode": mode,
        "sim_code": sim_code,
        "storage_root": str(storage_root),
        "temp_root": str(temp_root),
        "status_step": status_step,
        "curr_step": curr_step,
        "latest_movement_step": latest_movement,
        "latest_environment_step": latest_environment,
        "movement_file_count": len(movement_steps),
        "environment_file_count": len(environment_steps),
        "checks": checks,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check real runtime consistency across sim_status, curr_step, movement, and environment files."
    )
    parser.add_argument("--sim-code", default="curr_sim", help="Simulation code/folder under storage.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    parser.add_argument("--mode", choices=["ui", "headless"], default="ui")
    parser.add_argument(
        "--allowed-status-lag",
        type=int,
        default=1,
        help="Max accepted latest_movement - sim_status.step lag. Use 1 for live UI consistency.",
    )
    parser.add_argument(
        "--allowed-curr-step-lag",
        type=int,
        default=1,
        help="Max accepted distance between curr_step pointer and movement/environment edge.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_report(
        sim_code=args.sim_code,
        storage_root=args.storage_root,
        temp_root=args.temp_root,
        mode=args.mode,
        allowed_status_lag=args.allowed_status_lag,
        allowed_curr_step_lag=args.allowed_curr_step_lag,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Runtime consistency: {'PASS' if report['passed'] else 'FAIL'}")
        print(
            "steps: "
            f"status={report['status_step']} | "
            f"curr_step={report['curr_step']} | "
            f"movement={report['latest_movement_step']} | "
            f"environment={report['latest_environment_step']}"
        )
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"- {mark}: {check['name']} -> {check['detail']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
