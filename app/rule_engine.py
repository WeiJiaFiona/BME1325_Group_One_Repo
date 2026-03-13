from app.constants import RED_KEYWORDS, SEX_MAP, SYMPTOM_KEYWORDS, TRAUMA_KEYWORDS, YELLOW_KEYWORDS
from app.schemas import SessionContext, TriageLevel, TriageResponse


def normalize_sex(value: str) -> str:
    return SEX_MAP.get(value.strip().lower(), SEX_MAP.get(value.strip(), "未知"))


def normalize_symptom_label(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return value
    return SYMPTOM_KEYWORDS.get(text, value.strip())


def unique_extend(existing: list[str], additions: list[str]) -> list[str]:
    seen = set(existing)
    merged = list(existing)
    for item in additions:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def get_numeric_vital(vital_signs: dict[str, str | int | float], aliases: set[str]) -> float | None:
    for key, value in vital_signs.items():
        if key.lower() not in aliases:
            continue
        try:
            return float(str(value).split()[0])
        except ValueError:
            continue
    return None


def compute_missing_required_fields(context: SessionContext) -> list[str]:
    missing: list[str] = []
    if context.temperature is None and context.fever_present is None and context.temperature_status != "未知":
        missing.append("体温")
    if context.duration is None and context.onset_time is None:
        missing.append("起病时间")
    if context.trauma_history is None:
        missing.append("外伤史")
    return missing


def build_combined_text(context: SessionContext) -> str:
    message_text = " ".join(
        turn.message.lower() for turn in context.conversation_history if turn.role == "患者"
    )
    symptom_text = " ".join(context.symptoms + context.associated_symptoms + context.suspected_risk_signals)
    parts = [context.chief_complaint.lower(), symptom_text.lower(), message_text]
    return " ".join(part for part in parts if part)


def recommend_outpatient_entry(context: SessionContext, triage_level: TriageLevel) -> str:
    if triage_level == "红区":
        return "急诊"

    combined_text = build_combined_text(context)

    if context.trauma_history:
        return "急诊"
    if context.age < 10 and "腹痛" in combined_text:
        return "儿科"
    if context.age < 14 and contains_any(combined_text, ["咽痛", "咳嗽", "发热"]):
        return "儿科"
    if contains_any(combined_text, ["咽痛", "吞咽疼痛", "吞咽困难", "声音嘶哑"]):
        return "耳鼻喉科门诊"
    if "腹痛" in combined_text:
        return "普通外科"
    if contains_any(combined_text, ["胸痛", "发热", "咳嗽"]):
        return "内科门诊"
    return "全科门诊"


def evaluate_triage_context(context: SessionContext) -> TriageResponse:
    combined_text = build_combined_text(context)
    risk_flags: list[str] = []
    rule_engine_hits: list[str] = []

    if context.temperature is None:
        if context.temperature_status == "未知":
            risk_flags.append("体温未知")
            rule_engine_hits.append("必填项校验：患者暂时无法提供体温")
        elif context.fever_present is True:
            risk_flags.append("口述发热")
            rule_engine_hits.append("体温规则：已记录患者口述存在发热，待补充具体体温数值")
        elif context.fever_present is False:
            rule_engine_hits.append("体温规则：已记录患者口述目前未发热，允许继续分诊")
        else:
            risk_flags.append("缺少体温")
            rule_engine_hits.append("必填项校验：体温尚未采集")
    elif context.temperature >= 38.0:
        risk_flags.append("发热")
        rule_engine_hits.append("体温规则：体温 >= 38.0℃")

    if context.age < 10:
        risk_flags.append("儿童患者")

    if context.trauma_history or contains_any(combined_text, TRAUMA_KEYWORDS):
        risk_flags.append("外伤相关")
        rule_engine_hits.append("创伤规则：存在外伤或车祸相关信息")

    if context.age < 10 and "腹痛" in combined_text:
        risk_flags.append("儿童腹痛分科保护")
        rule_engine_hits.append("边界防错：10 岁以下腹痛优先儿科")

    if "咽痛" in combined_text and not contains_any(combined_text, ["呼吸困难", "气短"]):
        rule_engine_hits.append("分科规则：单纯咽痛优先耳鼻喉科或儿科门诊，不默认急诊")

    llm_hidden_critical_hint = contains_any(" ".join(context.suspected_risk_signals), ["疑似隐匿性出血", "休克风险"])
    if llm_hidden_critical_hint:
        rule_engine_hits.append("LLM 提示：检测到隐性危重风险，已进入规则复核")

    hidden_critical = (
        context.trauma_history is True
        and "极度口渴" in combined_text
        and "嗜睡" in combined_text
    ) or (context.trauma_history is True and llm_hidden_critical_hint)
    if hidden_critical:
        risk_flags.append("疑似隐匿性出血")
        rule_engine_hits.append("隐性危重规则：外伤 + 极度口渴 + 嗜睡 / LLM 风险信号确认")

    spo2 = get_numeric_vital(context.vital_signs, {"spo2", "oxygen_saturation"})
    systolic_bp = get_numeric_vital(context.vital_signs, {"systolic_bp", "sbp"})
    heart_rate = get_numeric_vital(context.vital_signs, {"heart_rate", "hr", "pulse"})
    respiratory_rate = get_numeric_vital(context.vital_signs, {"respiratory_rate", "rr"})

    if spo2 is not None and spo2 < 92:
        risk_flags.append("血氧偏低")
        rule_engine_hits.append("生命体征规则：SpO2 < 92")
    if systolic_bp is not None and systolic_bp < 90:
        risk_flags.append("低血压")
        rule_engine_hits.append("生命体征规则：收缩压 < 90")
    if heart_rate is not None and heart_rate > 130:
        risk_flags.append("心动过速")
        rule_engine_hits.append("生命体征规则：心率 > 130")
    if respiratory_rate is not None and respiratory_rate > 30:
        risk_flags.append("呼吸急促")
        rule_engine_hits.append("生命体征规则：呼吸频率 > 30")

    severe_vital_trigger = contains_any(" ".join(risk_flags), ["血氧偏低", "低血压", "心动过速", "呼吸急促"])
    upper_airway_urgent = contains_any(combined_text, ["吞咽困难"])
    red_trigger = (
        contains_any(combined_text, RED_KEYWORDS)
        or context.pain_score >= 9
        or hidden_critical
        or severe_vital_trigger
    )
    yellow_trigger = (
        contains_any(combined_text, YELLOW_KEYWORDS)
        or context.pain_score >= 5
        or context.fever_present is True
        or upper_airway_urgent
    )

    if red_trigger:
        triage_level: TriageLevel = "红区"
        need_emergency_transfer = True
        risk_flags = unique_extend(risk_flags, ["红旗征象触发"])
        rule_engine_hits.append("分诊规则：命中红区条件")
    elif yellow_trigger:
        triage_level = "黄区"
        need_emergency_transfer = False
        rule_engine_hits.append("分诊规则：命中黄区条件")
    else:
        triage_level = "绿区"
        need_emergency_transfer = False
        rule_engine_hits.append("分诊规则：命中绿区条件")

    recommended_outpatient_entry = recommend_outpatient_entry(context, triage_level)

    return TriageResponse(
        triage_level=triage_level,
        risk_flags=unique_extend([], risk_flags),
        need_emergency_transfer=need_emergency_transfer,
        recommended_outpatient_entry=recommended_outpatient_entry,
        rule_engine_hits=unique_extend([], rule_engine_hits),
    )
