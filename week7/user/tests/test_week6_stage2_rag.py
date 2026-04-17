from app_core.app.api_v1 import (
    _ensure_user_session,
    reset_runtime_state,
    user_mode_chat_turn,
    user_mode_session_status,
)
from app_core.app.rag.protocol_retriever import retrieve_protocols


def setup_function():
    reset_runtime_state()


def _reach_doctor(seed_complaint: str):
    user_mode_chat_turn(seed_complaint)
    called = None
    for _ in range(10):
        called = user_mode_session_status()
        if called["session"]["phase"] == "DOCTOR_CALLED":
            return called
    if called and called["session"]["phase"] != "DOCTOR_CALLED":
        called = user_mode_chat_turn("status update")
    return called


def _latest_followup_text(resp):
    arr = [
        m["text"]
        for m in resp.get("pending_messages", [])
        if m.get("role") == "doctor" and m.get("event_type") == "doctor_followup"
    ]
    return arr[-1] if arr else ""


def test_stage2_routes_to_stroke_protocol_question():
    called = _reach_doctor("突然口角歪斜，一侧无力，像中风")
    assert called["session"]["phase"] == "DOCTOR_CALLED"

    turn = user_mode_chat_turn("我一小时前突然说话不清")
    text = _latest_followup_text(turn)
    assert text
    assert (
        "最后一次正常" in text
        or "最后一次完全正常" in text
        or ("last known well" in text.lower())
    )


def test_stage2_routes_to_trauma_protocol_question():
    called = _reach_doctor("我摔倒了，可能骨折")
    assert called["session"]["phase"] == "DOCTOR_CALLED"

    turn = user_mode_chat_turn("肋骨像断了")
    text = _latest_followup_text(turn)
    assert text
    zh_semantic_match = ("受伤" in text and ("什么时候" in text or "时间" in text))
    assert (
        zh_semantic_match
        or ("injury happen" in text.lower())
        or ("when did" in text.lower())
    )


def test_stage2_critical_vitals_hard_override_to_resus():
    called = _reach_doctor("胸口疼")
    assert called["session"]["phase"] == "DOCTOR_CALLED"

    user_mode_chat_turn("spo2 85 sbp 80")
    sess = _ensure_user_session()
    assess = sess.get("shared_memory", {}).get("doctor_assessment", {})
    plan = assess.get("plan_contract", {})
    trace = assess.get("planner_trace", [])
    assert plan.get("urgency_proposed") == "RESUS"
    assert plan.get("disposition_proposed") == "ICU"
    assert trace
    assert trace[-1].get("validator_result") in {"pass", "hard_override", "soft_override"}


def test_stage2_negation_updates_slot_and_avoids_repeat():
    called = _reach_doctor("我胸口疼")
    assert called["session"]["phase"] == "DOCTOR_CALLED"
    user_mode_chat_turn("昨天上午开始")
    turn = user_mode_chat_turn("No shortness of breath")
    text = _latest_followup_text(turn).lower()
    # Breathing slot is filled by negation; follow-up should move on.
    assert "short of breath right now" not in text


def test_stage2_dedup_filled_duration_not_reasked():
    called = _reach_doctor("I have chest pain")
    assert called["session"]["phase"] == "DOCTOR_CALLED"
    turn1 = user_mode_chat_turn("yesterday morning")
    q1 = _latest_followup_text(turn1).lower()
    assert "when did the symptom start" not in q1


def test_stage25_case_bank_retrieval_hits_fuzzy_stroke_expression():
    out = retrieve_protocols(
        chief_complaint="嘴歪手麻，说话不清",
        symptoms=["突然一侧无力"],
        patient_message="家属说突然口角歪斜",
        vitals={"spo2": 97, "sbp": 132},
    )
    assert out["primary_protocol_id"] == "stroke"
    assert out.get("case_result", {}).get("case_refs")
    assert any(ref.get("section") == "case_bank" for ref in out.get("evidence_refs", []))


def test_stage25_case_protocol_added_as_secondary_when_supported():
    out = retrieve_protocols(
        chief_complaint="胸痛并且喘不上气",
        symptoms=["shortness of breath"],
        patient_message="胸口很闷并且气促",
        vitals={"spo2": 93, "sbp": 122},
    )
    assert out["primary_protocol_id"] in {"chest_pain", "dyspnea"}
    assert "dyspnea" in out.get("secondary_protocol_ids", []) or out["primary_protocol_id"] == "dyspnea"


def test_stage25_labor_protocol_selected_for_delivery_language():
    out = retrieve_protocols(
        chief_complaint="我要生小孩了，羊水破了",
        symptoms=["宫缩", "想用力"],
        patient_message="每5分钟宫缩一次",
        vitals={"spo2": 98, "sbp": 118},
    )
    assert out["primary_protocol_id"] == "labor"
    assert any(ref.get("section") == "case_bank" for ref in out.get("evidence_refs", []))


def test_stage25_anaphylaxis_protocol_selected_for_allergy_airway_signs():
    out = retrieve_protocols(
        chief_complaint="过敏反应，喉咙紧",
        symptoms=["荨麻疹", "呼吸困难"],
        patient_message="吃了花生后出现喘鸣",
        vitals={"spo2": 93, "sbp": 122},
    )
    assert out["primary_protocol_id"] == "anaphylaxis"


def test_stage25_headache_protocol_selected_for_severe_headache():
    out = retrieve_protocols(
        chief_complaint="我头很疼，剧烈头痛",
        symptoms=["头痛", "恶心"],
        patient_message="昨天开始，今天更严重",
        vitals={"spo2": 97, "sbp": 122},
    )
    assert out["primary_protocol_id"] == "headache"
