from week5_system.app.api_v1 import (
    reset_runtime_state,
    user_mode_chat_turn,
    user_mode_session_status,
)


def setup_function():
    reset_runtime_state()


def test_user_mode_calling_nurse_measures_then_triage_flow():
    first = user_mode_chat_turn("I feel chest pain and shortness of breath")
    # Patient should not be blocked on manual vitals.
    assert first["session"]["phase"] in {"WAITING_CALL", "DOCTOR_CALLED"}
    assert first["session"]["encounter_id"]
    roles = [m["role"] for m in first["messages"]]
    assert "calling_nurse" in roles
    assert "triage_nurse" in roles
    assert any("Triage completed:" in m["text"] for m in first["messages"] if m["role"] == "triage_nurse")


def test_user_mode_no_wait_message_when_queue_is_zero():
    first = user_mode_chat_turn("mild cough")
    if first["session"]["queue_position"] == 0:
        wait_lines = [
            m["text"] for m in first["messages"]
            if m["role"] == "calling_nurse" and "Please wait" in m["text"]
        ]
        assert wait_lines == []


def test_user_mode_waiting_auto_handoff_without_extra_hello():
    first = user_mode_chat_turn("mild abdominal pain")
    assert first["session"]["encounter_id"]

    # Poll status; if queue reaches turn, doctor prompt should appear without user text.
    for _ in range(8):
        status = user_mode_session_status()
        if status["session"]["phase"] == "DOCTOR_CALLED":
            break
    assert status["session"]["phase"] in {"WAITING_CALL", "DOCTOR_CALLED"}

    if status["session"]["phase"] == "DOCTOR_CALLED":
        pending_roles = [m["role"] for m in status.get("pending_messages", [])]
        assert (
            status["session"]["current_agent"] == "doctor"
            or "doctor" in pending_roles
            or any(m["role"] == "doctor" for m in status.get("messages", []))
        )


def test_user_mode_doctor_then_bed_nurse_completion_path():
    user_mode_chat_turn("severe headache and vomiting")

    # Reach doctor phase via polling instead of forced user smalltalk.
    called = None
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break

    if called["session"]["phase"] != "DOCTOR_CALLED":
        # Trigger one user message if still waiting in queue under current runtime.
        called = user_mode_chat_turn("status update")

    assert called["session"]["phase"] == "DOCTOR_CALLED"

    doctor_turn_1 = user_mode_chat_turn("Pain started 2 hours ago.")
    assert doctor_turn_1["session"]["phase"] in {"DOCTOR_CALLED", "BED_NURSE_FLOW", "DONE"}

    doctor_turn_2 = user_mode_chat_turn("No fever, breathing is okay.")
    assert doctor_turn_2["session"]["phase"] in {"BED_NURSE_FLOW", "DONE"}

    # Bed nurse flow can auto-complete on status polling.
    if doctor_turn_2["session"]["phase"] == "BED_NURSE_FLOW":
        final_status = user_mode_session_status()
        assert final_status["session"]["phase"] == "DONE"


def test_user_mode_status_returns_pending_and_memory_version():
    user_mode_chat_turn("abdominal pain")
    status = user_mode_session_status()
    assert "session" in status
    assert "transcript_tail" in status
    assert "pending_messages" in status
    assert "memory_version" in status["session"]
    assert status["session"]["patient_id"] == "Patient 1"
