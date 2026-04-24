from app_core.app.api_v1 import (
    reset_runtime_state,
    user_mode_chat_turn,
    user_mode_session_status,
)


def setup_function():
    reset_runtime_state()


def test_doctor_smalltalk_does_not_immediately_finish_encounter():
    user_mode_chat_turn("I have chest pain")

    # Let queue progress automatically if needed.
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("status update")
    assert called["session"]["phase"] == "DOCTOR_CALLED"

    smalltalk = user_mode_chat_turn("hello")
    assert smalltalk["session"]["phase"] == "DOCTOR_CALLED"
    assert any(m["role"] == "doctor" for m in smalltalk["messages"])

    detail_1 = user_mode_chat_turn(
        "Pain started 2 hours ago, no fever, breathing is okay, pain not worsening."
    )
    assert detail_1["session"]["phase"] in {"DOCTOR_CALLED", "BED_NURSE_FLOW", "DONE"}


def test_typo_and_compact_input_still_allows_progress_without_manual_vitals():
    first = user_mode_chat_turn("Ihavepheomoniabefore and my chest hurts")
    assert first["session"]["phase"] in {"WAITING_CALL", "DOCTOR_CALLED"}
    assert first["session"]["encounter_id"]
    assert any(m["role"] == "calling_nurse" for m in first["messages"])


def test_greeting_first_prompts_for_complaint():
    first = user_mode_chat_turn("hello")
    assert first["session"]["phase"] == "INTAKE"
    assert first["messages"]
    assert first["messages"][0]["role"] == "triage_nurse"


def test_green_channel_bypasses_waiting_queue_after_calling_nurse_measurement():
    second = user_mode_chat_turn("我胸口很闷而且呼吸困难，严重，快晕了")
    assert second["session"]["phase"] == "DOCTOR_CALLED"
    assert second["session"]["current_agent"] == "doctor"
    assert second["session"]["queue_position"] == 0
    assert any(m["role"] == "doctor" for m in second["messages"])


def test_memory_version_increases_across_roles():
    r1 = user_mode_chat_turn("abdominal pain")
    v1 = r1["session"]["memory_version"]

    r2 = user_mode_session_status()
    v2 = r2["session"]["memory_version"]

    assert v2 >= v1


def test_doctor_asks_one_focused_question_per_turn():
    user_mode_chat_turn("I have chest pain")
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("status update")

    turn = user_mode_chat_turn("hello doctor")
    doctor_msgs = [m["text"] for m in turn["messages"] if m["role"] == "doctor"]
    assert doctor_msgs
    followups = [
        m for m in turn.get("pending_messages", [])
        if m.get("role") == "doctor" and m.get("event_type") == "doctor_followup"
    ]
    if followups:
        latest = followups[-1]["text"]
        question_count = latest.count("?") + latest.count("？")
        assert question_count <= 1
        assert question_count >= 1


def test_doctor_understands_free_form_without_template():
    user_mode_chat_turn("我胸口疼")
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("状态更新")

    # Free-form answer with mixed details; no strict template.
    step1 = user_mode_chat_turn("从昨天晚上开始，今天明显更痛，没有发烧，也不喘，没有放射到手臂下巴，也没有晕倒。")
    assert step1["session"]["phase"] in {"DOCTOR_CALLED", "BED_NURSE_FLOW", "DONE"}

    if step1["session"]["phase"] == "DOCTOR_CALLED":
        step2 = user_mode_chat_turn("大概3分，主要是持续性闷痛。")
        assert step2["session"]["phase"] in {"DOCTOR_CALLED", "BED_NURSE_FLOW", "DONE"}


def test_obstetric_complaint_uses_obstetric_single_question():
    user_mode_chat_turn("我要生小孩了")
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("状态更新")

    turn = user_mode_chat_turn("我的羊水破了")
    followups = [
        m["text"]
        for m in turn.get("pending_messages", [])
        if m.get("role") == "doctor" and m.get("event_type") == "doctor_followup"
    ]
    if followups:
        latest = followups[-1]
        assert "fever" not in latest.lower()
        assert "breath" not in latest.lower()
        assert latest.count("?") + latest.count("？") <= 1


def test_yes_no_short_answers_update_current_target_without_loop():
    user_mode_chat_turn("I have chest pain")
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("status update")

    user_mode_chat_turn("yesterday morning")
    first_yes = user_mode_chat_turn("yes")
    second_yes = user_mode_chat_turn("yes")

    def _latest_followup(resp):
        arr = [
            m["text"] for m in resp.get("pending_messages", [])
            if m.get("role") == "doctor" and m.get("event_type") == "doctor_followup"
        ]
        return arr[-1] if arr else ""

    q1 = _latest_followup(first_yes).lower()
    q2 = _latest_followup(second_yes).lower()
    assert q1 != ""
    assert q2 != ""
    assert q1 != q2


def test_doctor_answers_patient_imaging_question_before_followup():
    user_mode_chat_turn("我头很疼")
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("状态更新")

    turn = user_mode_chat_turn("我头疼，我应该去扫描什么影像？")
    doctor_msgs = [m["text"] for m in turn["messages"] if m["role"] == "doctor"]
    assert doctor_msgs
    merged = " ".join(doctor_msgs).lower()
    assert ("ct" in merged) or ("mri" in merged) or ("影像" in merged) or ("扫描" in merged)


def test_imaging_answer_does_not_embed_followup_question_twice():
    user_mode_chat_turn("我头很疼，9级，刚刚突然开始的，还恶心想吐。")
    for _ in range(8):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("状态更新")

    turn = user_mode_chat_turn("我这种头痛要做什么影像？CT还是MRI？")
    # Use pending_messages with event types to disambiguate answer vs followup ordering.
    answers = [
        m["text"]
        for m in turn.get("pending_messages", [])
        if m.get("role") == "doctor" and m.get("event_type") == "doctor_answer"
    ]
    assert answers
    answer = answers[-1]
    assert ("ct" in answer.lower()) or ("mri" in answer.lower()) or ("影像" in answer) or ("扫描" in answer)
    # The explanation should not embed a follow-up onset question.
    assert ("从什么时候开始" not in answer) and ("什么时候开始" not in answer)


def test_abdominal_pain_onset_in_free_form_is_not_re_asked_as_duration_loop():
    """
    Regression: if the patient already states onset in free-form CN (e.g. "从早上开始肚子疼"),
    the doctor should not ask the onset/duration question again immediately.
    """
    user_mode_chat_turn("你好")
    user_mode_chat_turn("我肚子疼，大概10级")
    # Let queue progress automatically if needed.
    for _ in range(10):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            break
    if called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("状态更新")
    assert called["session"]["phase"] == "DOCTOR_CALLED"

    turn1 = user_mode_chat_turn("我从早上开始肚子疼")
    followups1 = [
        m["text"]
        for m in turn1.get("pending_messages", [])
        if m.get("role") == "doctor" and m.get("event_type") == "doctor_followup"
    ]
    if followups1:
        q1 = followups1[-1]
        assert "什么时候开始" not in q1
        assert "从什么时候" not in q1
