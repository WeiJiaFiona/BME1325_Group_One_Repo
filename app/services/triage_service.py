from uuid import uuid4

from app.rule_engine import (
    compute_missing_required_fields,
    evaluate_triage_context,
    normalize_sex,
    normalize_symptom_label,
)
from app.schemas import (
    ConversationTurn,
    IntakeInput,
    SessionContext,
    SessionMessageResponse,
    SessionStartResponse,
    SessionStateResponse,
    TriageRequest,
    TriageResponse,
)
from app.services.feature_extractor import extract_features_from_message
from app.services.llm_service import generate_followup_question
from app.session_store import session_store


def infer_fever_from_temperature(temperature: float | None) -> bool | None:
    if temperature is None:
        return None
    if temperature >= 38.0:
        return True
    if temperature < 37.5:
        return False
    return None


def apply_updates_to_context(context: SessionContext, updates: dict) -> None:
    if "temperature" in updates:
        context.temperature = updates["temperature"]
    if "temperature_status" in updates:
        context.temperature_status = updates["temperature_status"]
        if updates["temperature_status"] == "未知":
            context.temperature = None
    if "fever_present" in updates:
        context.fever_present = updates["fever_present"]
    elif "temperature" in updates:
        context.fever_present = infer_fever_from_temperature(updates["temperature"])
    if "pain_score" in updates:
        context.pain_score = updates["pain_score"]
    if "duration" in updates:
        context.duration = updates["duration"]
    if "onset_time" in updates:
        context.onset_time = updates["onset_time"]
    if "severity" in updates:
        context.severity = updates["severity"]
    if "trauma_history" in updates:
        context.trauma_history = updates["trauma_history"]
    if "symptoms" in updates:
        context.symptoms = list(dict.fromkeys(context.symptoms + updates["symptoms"]))
    if "associated_symptoms" in updates:
        context.associated_symptoms = list(dict.fromkeys(context.associated_symptoms + updates["associated_symptoms"]))
    if "suspected_risk_signals" in updates:
        context.suspected_risk_signals = list(dict.fromkeys(context.suspected_risk_signals + updates["suspected_risk_signals"]))


def choose_next_question(context: SessionContext, triage_result: TriageResponse) -> str:
    symptom_text = " ".join(context.symptoms + context.associated_symptoms)

    if triage_result.triage_level == "红区":
        return "系统已经识别到需要尽快线下处理的危险信号，请立即前往急诊或呼叫急救，不要继续等待普通门诊。"

    if "体温" in context.missing_required_fields:
        return "如果方便的话，想补充一下刚测的体温。你可以直接回复“36.6℃”“体温正常”，或者“还没量”。"
    if "起病时间" in context.missing_required_fields:
        return "我先确认一下，这次不舒服大概是从什么时候开始的？比如今天、昨天，或者已经持续好几天了。"
    if "外伤史" in context.missing_required_fields:
        return "另外确认一下，最近有没有摔伤、撞伤、车祸这类外伤情况？如果没有，直接回复“没有外伤”就可以。"
    if "腹痛" in symptom_text and not context.associated_symptoms:
        return "我再补问一句：除了腹痛之外，还有没有呕吐、腹泻、出血、嗜睡或者呼吸不舒服？"
    if "咽痛" in symptom_text and not any(item in symptom_text for item in ["吞咽疼痛", "吞咽困难", "声音嘶哑", "咳嗽"]):
        return "想再了解一下喉咙这边的情况：吞咽时会不会更疼？有没有咳嗽、声音嘶哑，或者呼吸不顺？"

    llm_question = generate_followup_question(context, triage_result)
    if llm_question:
        return llm_question

    if context.temperature is None and context.fever_present is not None:
        fever_hint = "目前没有明显发热" if context.fever_present is False else "目前有发热表现"
        return f"已记下你提到“{fever_hint}”。如果方便，后面也可以补充一个具体体温数值；同时如果还有其他不适，也可以继续告诉我。"

    return "目前已经形成初步分诊结果。如果你还想补充新的症状、持续时间或检查结果，我会继续更新判断。"


def refresh_session_context(context: SessionContext) -> TriageResponse:
    triage_result = evaluate_triage_context(context)
    context.risk_flags = triage_result.risk_flags
    context.rule_engine_hits = triage_result.rule_engine_hits
    context.triage_level = triage_result.triage_level
    context.need_emergency_transfer = triage_result.need_emergency_transfer
    context.recommended_outpatient_entry = triage_result.recommended_outpatient_entry
    context.missing_required_fields = compute_missing_required_fields(context)
    context.next_question = choose_next_question(context, triage_result)
    return triage_result


def build_context_from_intake(session_id: str, payload: IntakeInput) -> SessionContext:
    temperature_status = "已知"
    if payload.temperature is None:
        temperature_status = "缺失"

    initial_trace = {
        "raw_text": payload.chief_complaint,
        "regex_hits": {},
        "keyword_hits": [f"主诉:{payload.chief_complaint}"],
        "lay_phrase_hits": [],
        "llm_updates": {},
        "merged_updates": {"symptoms": [normalize_symptom_label(payload.chief_complaint)]},
    }

    return SessionContext(
        session_id=session_id,
        chief_complaint=payload.chief_complaint,
        age=payload.age,
        sex=normalize_sex(payload.sex),
        temperature=payload.temperature,
        temperature_status=temperature_status,
        fever_present=infer_fever_from_temperature(payload.temperature),
        pain_score=payload.pain_score,
        vital_signs=payload.vital_signs or {},
        symptoms=[normalize_symptom_label(payload.chief_complaint)],
        last_extraction_trace=initial_trace,
        conversation_history=[ConversationTurn(role="患者", message=payload.chief_complaint)],
    )


def single_shot_triage(payload: TriageRequest) -> TriageResponse:
    context = build_context_from_intake(session_id="single-shot", payload=payload)
    return refresh_session_context(context)


def start_session(payload: IntakeInput) -> SessionStartResponse:
    session_id = str(uuid4())
    context = build_context_from_intake(session_id=session_id, payload=payload)
    triage_result = refresh_session_context(context)
    assistant_message = context.next_question or "会话已创建。"
    context.conversation_history.append(ConversationTurn(role="助手", message=assistant_message))
    session_store.save(context)
    return SessionStartResponse(
        session_id=session_id,
        assistant_message=assistant_message,
        triage_result=triage_result,
        session_context=context,
    )


def process_session_message(session_id: str, message: str) -> SessionMessageResponse | None:
    context = session_store.get(session_id)
    if context is None:
        return None

    context.conversation_history.append(ConversationTurn(role="患者", message=message))
    extraction_bundle = extract_features_from_message(message, context)
    apply_updates_to_context(context, extraction_bundle.merged_updates)
    context.last_extraction_trace = extraction_bundle.trace
    triage_result = refresh_session_context(context)
    assistant_message = context.next_question or "已收到患者回复。"
    context.conversation_history.append(ConversationTurn(role="助手", message=assistant_message))
    session_store.save(context)
    return SessionMessageResponse(
        session_id=context.session_id,
        assistant_message=assistant_message,
        extracted_updates=extraction_bundle.display_updates,
        extraction_trace=extraction_bundle.trace,
        triage_result=triage_result,
        session_context=context,
    )


def get_session_state(session_id: str) -> SessionStateResponse | None:
    context = session_store.get(session_id)
    if context is None:
        return None

    triage_result = refresh_session_context(context)
    session_store.save(context)
    return SessionStateResponse(
        session_id=context.session_id,
        triage_result=triage_result,
        session_context=context,
    )
