from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8010"


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _build_environment_payload(update_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    environment: Dict[str, Dict[str, Any]] = {}
    for persona_name, persona_payload in (update_payload.get("persona") or {}).items():
        movement = persona_payload.get("movement") or [0, 0]
        environment[persona_name] = {
            "maze": "ed_map",
            "x": int(movement[0]),
            "y": int(movement[1]),
        }
    return environment


def _classify(runtime_sync: Dict[str, Any], backend_health: Dict[str, Any]) -> str:
    latest_movement = runtime_sync.get("latest_movement_step")
    latest_environment = runtime_sync.get("latest_environment_step")
    if backend_health.get("stalled") or not backend_health.get("backend_alive"):
        return "backend movement stalled"
    if runtime_sync.get("in_sync"):
        return "frontend bridge healthy"
    if latest_movement is not None and latest_environment is not None and int(latest_movement) > int(latest_environment):
        return "bridge write-back lag"
    return "frontend bridge healthy"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate the browser bridge loop for auto mode.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--sim-code", default="curr_sim")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-polls", type=int, default=20)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    session = requests.Session()
    session.trust_env = False

    reconciled_steps = 0
    poll_index = 0

    while reconciled_steps < args.max_steps and poll_index < args.max_polls:
        poll_index += 1
        dashboard_resp = session.get(f"{args.base_url}/api/live_dashboard/", timeout=10)
        dashboard_payload = _safe_json(dashboard_resp)
        if dashboard_resp.status_code != 200:
            print(json.dumps({
                "poll": poll_index,
                "classification": "backend movement stalled",
                "dashboard_http": dashboard_resp.status_code,
                "dashboard": dashboard_payload,
            }, ensure_ascii=False))
            return 1

        runtime_sync = dashboard_payload.get("runtime_sync") or {}
        backend_health = dashboard_payload.get("backend_health") or {}
        latest_movement = runtime_sync.get("latest_movement_step")
        latest_environment = runtime_sync.get("latest_environment_step")
        status_step = runtime_sync.get("status_step")

        print(json.dumps({
            "poll": poll_index,
            "status_step": status_step,
            "latest_movement_step": latest_movement,
            "latest_environment_step": latest_environment,
            "in_sync": runtime_sync.get("in_sync"),
            "backend_alive": backend_health.get("backend_alive"),
            "stalled": backend_health.get("stalled"),
        }, ensure_ascii=False))

        if runtime_sync.get("in_sync") and reconciled_steps > 0:
            print(json.dumps({
                "classification": "frontend bridge healthy",
                "reconciled_steps": reconciled_steps,
                "runtime_sync": runtime_sync,
            }, ensure_ascii=False))
            return 0

        if latest_movement is None or latest_environment is None:
            time.sleep(args.poll_seconds)
            continue

        start_step = int(latest_environment) + 1
        end_step = min(int(latest_movement), start_step + (args.max_steps - reconciled_steps) - 1)

        if start_step > end_step:
            time.sleep(args.poll_seconds)
            continue

        for step in range(start_step, end_step + 1):
            update_resp = session.post(
                f"{args.base_url}/update_environment/",
                json={"step": step, "sim_code": args.sim_code},
                timeout=10,
            )
            update_payload = _safe_json(update_resp)
            update_ok = update_resp.status_code == 200 and int(update_payload.get("<step>", -1)) == step

            print(json.dumps({
                "bridge": "update_environment",
                "step": step,
                "http": update_resp.status_code,
                "ok": update_ok,
            }, ensure_ascii=False))

            if not update_ok:
                print(json.dumps({
                    "classification": "backend movement stalled",
                    "step": step,
                    "payload": update_payload,
                }, ensure_ascii=False))
                return 1

            env_payload = _build_environment_payload(update_payload)
            process_resp = session.post(
                f"{args.base_url}/process_environment/",
                json={"step": step, "sim_code": args.sim_code, "environment": env_payload},
                timeout=10,
            )
            process_payload = _safe_json(process_resp)
            process_ok = process_resp.status_code == 200 and bool(process_payload.get("ok"))

            print(json.dumps({
                "bridge": "process_environment",
                "step": step,
                "http": process_resp.status_code,
                "ok": process_ok,
            }, ensure_ascii=False))

            if not process_ok:
                print(json.dumps({
                    "classification": "bridge write-back lag",
                    "step": step,
                    "payload": process_payload,
                }, ensure_ascii=False))
                return 1

            reconciled_steps += 1
            if reconciled_steps >= args.max_steps:
                break

        time.sleep(args.poll_seconds)

    final_resp = session.get(f"{args.base_url}/api/live_dashboard/", timeout=10)
    final_payload = _safe_json(final_resp)
    runtime_sync = final_payload.get("runtime_sync") or {}
    backend_health = final_payload.get("backend_health") or {}
    classification = _classify(runtime_sync, backend_health)
    print(json.dumps({
        "classification": classification,
        "reconciled_steps": reconciled_steps,
        "runtime_sync": runtime_sync,
        "backend_health": backend_health,
    }, ensure_ascii=False))
    return 0 if classification == "frontend bridge healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
