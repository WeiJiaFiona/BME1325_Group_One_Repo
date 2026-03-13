from typing import Any

from bailian_client import BailianAPIError, extract_triage_updates, is_bailian_configured, query_bailian

from app.rule_engine import normalize_symptom_label
from app.schemas import SessionContext, TriageResponse


def query_model(
    query: str,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    return query_bailian(
        query=query,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
    )


def session_snapshot_from_context(context: SessionContext) -> dict[str, Any]:
    return {
        "chief_complaint": context.chief_complaint,
        "age": context.age,
        "sex": context.sex,
        "temperature": context.temperature,
        "temperature_status": context.temperature_status,
        "pain_score": context.pain_score,
        "symptoms": context.symptoms,
        "associated_symptoms": context.associated_symptoms,
        "suspected_risk_signals": context.suspected_risk_signals,
        "onset_time": context.onset_time,
        "duration": context.duration,
        "severity": context.severity,
        "trauma_history": context.trauma_history,
        "triage_level": context.triage_level,
        "recommended_outpatient_entry": context.recommended_outpatient_entry,
        "missing_required_fields": context.missing_required_fields,
    }


def triage_result_snapshot(triage_result: TriageResponse) -> dict[str, Any]:
    if hasattr(triage_result, "model_dump"):
        return triage_result.model_dump()
    return triage_result.dict()


def extract_updates_with_llm(message: str, context: SessionContext) -> dict[str, Any]:
    if not is_bailian_configured():
        return {}

    llm_updates = extract_triage_updates(
        message=message,
        session_snapshot=session_snapshot_from_context(context),
    )
    return {
        key: [normalize_symptom_label(item) for item in value] if key in {"symptoms", "associated_symptoms"} else value
        for key, value in llm_updates.items()
    }


def generate_followup_question(context: SessionContext, triage_result: TriageResponse) -> str | None:
    if triage_result.triage_level == "红区" or not is_bailian_configured():
        return None

    system_prompt = (
        "你是医院分诊追问助手。"
        "请根据当前上下文，只生成一句最重要的中文追问。"
        "不要诊断疾病，不要一次问多个问题，不要输出编号、解释或多余内容。"
        "如果已足够分诊，请输出：目前信息已基本完整，请确认是否还有其他不适。"
    )
    user_prompt = (
        f"当前会话上下文：{session_snapshot_from_context(context)}\n"
        f"当前分诊结果：{triage_result_snapshot(triage_result)}\n"
        "请给出下一句最关键的追问。"
    )

    try:
        result = query_model(
            query=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )
    except Exception:
        # Follow-up generation is non-critical. If the LLM times out or
        # returns an unexpected payload, fall back to rule-based questions.
        return None

    content = result.get("content", "").strip()
    return content or None


