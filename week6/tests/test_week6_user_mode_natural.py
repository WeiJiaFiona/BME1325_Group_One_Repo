from week5_system.app.api_v1 import (
    reset_runtime_state,
    user_mode_chat_turn,
)


def setup_function():
    reset_runtime_state()


def test_doctor_smalltalk_does_not_immediately_finish_encounter():
    user_mode_chat_turn("I have chest pain")
    user_mode_chat_turn("spo2 95 sbp 120")
    called = user_mode_chat_turn("status update")
    assert called["session"]["phase"] == "DOCTOR_CALLED"

    smalltalk = user_mode_chat_turn("hello")
    assert smalltalk["session"]["phase"] == "DOCTOR_CALLED"
    assert smalltalk["messages"]
    assert smalltalk["messages"][0]["role"] == "doctor"

    detail_1 = user_mode_chat_turn(
        "Pain started 2 hours ago, no fever, breathing is okay, pain not worsening."
    )
    assert detail_1["session"]["phase"] == "DOCTOR_CALLED"

    detail_2 = user_mode_chat_turn("I had pheomonia before and still feel chest pressure.")
    assert detail_2["session"]["phase"] in {"BED_NURSE_FLOW", "DONE"}


def test_typo_and_compact_input_still_allows_intake_progress():
    first = user_mode_chat_turn("Ihavepheomoniabefore and my chest hurts")
    assert first["session"]["phase"] == "INTAKE"
    assert first["messages"]

    second = user_mode_chat_turn("spo2 95")
    assert second["session"]["phase"] == "INTAKE"

    third = user_mode_chat_turn("sbp 120")
    assert third["session"]["phase"] == "WAITING_CALL"
    assert third["messages"]
    assert third["messages"][0]["role"] == "triage_nurse"


def test_greeting_first_prompts_for_complaint_not_vitals():
    first = user_mode_chat_turn("hello")
    assert first["session"]["phase"] == "INTAKE"
    assert first["messages"]
    assert first["messages"][0]["role"] == "triage_nurse"


def test_cannot_measure_vitals_nurse_can_fill_and_continue():
    user_mode_chat_turn("I have chest pain and feel anxious")
    follow = user_mode_chat_turn("I can't measure these right now")
    assert follow["messages"]
    assert follow["messages"][0]["role"] == "triage_nurse"
    # Keep progressing on the same turn or next turn, but should not be stuck forever on missing vitals.
    if follow["session"]["phase"] == "INTAKE":
        nxt = user_mode_chat_turn("ok")
        assert nxt["session"]["phase"] in {"WAITING_CALL", "DOCTOR_CALLED"}


def test_green_channel_bypasses_waiting_queue():
    user_mode_chat_turn("我胸口很闷而且呼吸困难")
    second = user_mode_chat_turn("spo2 30 sbp 70")
    assert second["session"]["phase"] == "DOCTOR_CALLED"
    assert second["session"]["current_agent"] == "doctor"
    assert second["session"]["queue_position"] == 0
    assert any(m["role"] == "doctor" for m in second["messages"])
