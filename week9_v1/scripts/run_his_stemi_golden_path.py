from __future__ import annotations

import json

from app_core.app.api_v1 import export_encounter_timeline, reset_runtime_state, user_mode_chat_turn, user_mode_session_status


def build_stemi_golden_path_plan() -> dict[str, object]:
    reset_runtime_state()
    turns = [
        "I have severe chest pain, shortness of breath, and cold sweat",
        "Pain started 30 minutes ago and is 9 out of 10",
        "It radiates to my left arm and I nearly fainted",
        "Breathing is hard and the pain is getting worse",
        "No fever",
        "No fainting before today but I feel worse now",
        "The pain is definitely getting worse",
    ]
    latest = None
    for message in turns:
        latest = user_mode_chat_turn(message)
        if latest["session"]["phase"] == "DONE":
            break
        if latest["session"]["phase"] != "DOCTOR_CALLED":
            latest = user_mode_session_status()
    for followup in ["No fever, breathing is still hard", "I almost fainted again"]:
        if latest is not None and latest["session"]["phase"] == "DONE":
            break
        if latest is not None and latest["session"]["phase"] == "DOCTOR_CALLED":
            latest = user_mode_chat_turn(followup)
    for _ in range(8):
        if latest is not None and latest["session"]["phase"] == "DONE":
            break
        latest = user_mode_session_status()
    if latest is None:
        raise RuntimeError("STEMI golden path did not produce any runtime state")
    timeline = export_encounter_timeline(latest["session"]["encounter_id"])
    bundle = timeline["bundle"]
    return {
        "name": "stemi_golden_path",
        "status": "passed" if latest["session"]["encounter_id"] and bundle["stemi_workup"]["orders"] else "failed",
        "scenario": "Chest pain with STEMI-like deterioration and higher-acuity disposition.",
        "final_phase": latest["session"]["phase"],
        "encounter_id": latest["session"]["encounter_id"],
        "stemi_workup_counts": {
            "orders": len(bundle["stemi_workup"]["orders"]),
            "lab_requests": len(bundle["stemi_workup"]["lab_requests"]),
            "lab_results": len(bundle["stemi_workup"]["lab_results"]),
            "imaging_requests": len(bundle["stemi_workup"]["imaging_requests"]),
            "imaging_results": len(bundle["stemi_workup"]["imaging_results"]),
        },
        "timeline_sections": sorted(bundle.keys()),
    }


def main() -> None:
    print(json.dumps(build_stemi_golden_path_plan(), indent=2))


if __name__ == "__main__":
    main()
