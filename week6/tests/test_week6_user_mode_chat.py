from week5_system.app.api_v1 import (
    reset_runtime_state,
    user_mode_chat_turn,
    user_mode_session_status,
)


def setup_function():
    reset_runtime_state()


def test_user_mode_intake_followup_then_encounter_start():
    first = user_mode_chat_turn("I feel chest pain")
    assert first["session"]["phase"] == "INTAKE"
    assert first["messages"]
    assert first["messages"][0]["role"] == "triage_nurse"

    second = user_mode_chat_turn("shortness of breath, dizziness, spo2 93 sbp 88")
    assert second["session"]["phase"] == "WAITING_CALL"
    assert second["session"]["encounter_id"]
    assert second["messages"]
    assert second["messages"][0]["role"] == "triage_nurse"


def test_user_mode_called_then_doctor_then_bed_nurse_flow():
    user_mode_chat_turn("severe headache")
    user_mode_chat_turn("vomiting, blurred vision, spo2 94 sbp 90")

    called = user_mode_chat_turn("status update")
    assert called["session"]["phase"] in {"DOCTOR_CALLED", "WAITING_CALL"}

    # Keep prompting until the queue reaches doctor.
    for _ in range(3):
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
        called = user_mode_chat_turn("check queue")
    assert called["session"]["phase"] == "DOCTOR_CALLED"
    assert called["session"]["current_agent"] == "doctor"

    doctor_turn_1 = user_mode_chat_turn("Pain started 2 hours ago.")
    assert doctor_turn_1["session"]["phase"] in {"DOCTOR_CALLED", "BED_NURSE_FLOW", "DONE"}

    doctor_turn_2 = user_mode_chat_turn("No fever, breathing is okay.")
    assert doctor_turn_2["session"]["phase"] in {"BED_NURSE_FLOW", "DONE"}

    if doctor_turn_2["session"]["phase"] == "BED_NURSE_FLOW":
        nurse = user_mode_chat_turn("okay")
        assert nurse["session"]["phase"] == "DONE"
        assert nurse["session"]["current_agent"] == "bed_nurse"


def test_user_mode_status_returns_session_and_tail():
    user_mode_chat_turn("abdominal pain")
    status = user_mode_session_status()
    assert "session" in status
    assert "transcript_tail" in status
    assert status["session"]["patient_id"] == "Patient 1"
