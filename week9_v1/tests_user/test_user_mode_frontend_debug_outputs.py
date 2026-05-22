from app_core.app.api_v1 import (
    export_encounter_timeline,
    reset_runtime_state,
    user_mode_chat_turn,
    user_mode_session_status,
)


def setup_function():
    reset_runtime_state()


def test_user_mode_output_analysis_covers_role_progression():
    phases = []
    roles_seen = set()
    agent_transitions = []

    first = user_mode_chat_turn("I have severe chest pain and shortness of breath")
    phases.append(first["session"]["phase"])
    roles_seen.update(message["role"] for message in first["messages"])
    agent_transitions.append(first["session"].get("current_agent"))

    latest = first
    for utterance in [
        "The pain started 30 minutes ago.",
        "It radiates to my left arm.",
        "I feel dizzy.",
        "No fever.",
    ]:
        if latest["session"]["phase"] == "DONE":
            break
        latest = user_mode_chat_turn(utterance)
        phases.append(latest["session"]["phase"])
        roles_seen.update(message["role"] for message in latest["messages"])
        agent_transitions.append(latest["session"].get("current_agent"))

    for _ in range(4):
        if latest["session"]["phase"] == "DONE":
            break
        latest = user_mode_session_status()
        phases.append(latest["session"]["phase"])
        roles_seen.update(message["role"] for message in latest.get("messages", []))
        roles_seen.update(message["role"] for message in latest.get("pending_messages", []))
        agent_transitions.append(latest["session"].get("current_agent"))

    timeline = export_encounter_timeline(latest["session"]["encounter_id"])
    bundle = timeline["bundle"]
    replay = bundle["memory_replay"]
    consistency = {
        "event_count_match": len(replay["events"]) == len(bundle["event_registry"]),
        "snapshot_count_match": len(replay["snapshots"]) == len(bundle["handoff_snapshots"]),
        "summary_state_match": bool(replay["summaries"]) and replay["summaries"][-1]["current_state"] == bundle["summary"]["current_state"],
    }
    summary = {
        "Backend flow status": phases,
        "Frontend render status": "backed_by_user_mode_payloads",
        "Avatar mapping status": sorted(roles_seen),
        "Collision/path status": timeline["document"]["document_type"],
        "Timeline export status": sorted(bundle.keys()),
        "Memory/HIS consistency": consistency,
        "Conclusion": latest["session"]["phase"],
    }
    print(summary)

    assert "calling_nurse" in roles_seen
    assert "triage_nurse" in roles_seen
    assert any(role in roles_seen for role in {"doctor", "bed_nurse"})
    assert timeline["document"]["document_type"] == "timeline_export"
    assert all(consistency.values())
    assert latest["session"]["phase"] in {"BED_NURSE_FLOW", "DONE", "DOCTOR_CALLED"}
    assert any(agent in {"doctor", "bed_nurse"} for agent in agent_transitions if agent)
