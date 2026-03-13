from dataclasses import dataclass
from typing import Any

from app.constants import ONSET_PHRASES, SYMPTOM_KEYWORDS, TRAUMA_KEYWORDS, UNKNOWN_TEMPERATURE_PHRASES
from app.rule_engine import contains_any, unique_extend
from app.schemas import SessionContext
from app.services.llm_service import extract_updates_with_llm

NEGATIVE_TRAUMA_PHRASES = [
    "no trauma",
    "not injured",
    "no injury",
    "无外伤",
    "没有外伤",
    "没受伤",
    "没有受伤",
]

NO_FEVER_PHRASES = [
    "体温正常",
    "温度正常",
    "没发烧",
    "没有发烧",
    "不发烧",
    "没发热",
    "没有发热",
    "不烧",
    "退烧了",
]

FEVERISH_PHRASES = [
    "发烧了",
    "有点发烧",
    "一直发烧",
    "感觉发烧",
    "感觉发热",
    "在发烧",
]

LAY_PHRASE_MAPPINGS: dict[str, dict[str, Any]] = {
    "喘不上气": {"symptoms": ["呼吸困难"], "associated_symptoms": ["呼吸困难"]},
    "呼不上来": {"symptoms": ["呼吸困难"], "associated_symptoms": ["呼吸困难"]},
    "胸口发闷": {"symptoms": ["胸痛"], "severity": "中度"},
    "胸口压得慌": {"symptoms": ["胸痛"], "severity": "重度"},
    "肚子绞着疼": {"symptoms": ["腹痛"], "severity": "重度"},
    "肚子疼得厉害": {"symptoms": ["腹痛"], "severity": "重度"},
    "一直想吐": {"symptoms": ["恶心"], "associated_symptoms": ["恶心"]},
    "老想吐": {"symptoms": ["恶心"], "associated_symptoms": ["恶心"]},
    "站不稳": {"symptoms": ["头晕"], "associated_symptoms": ["头晕"]},
    "眼前发黑": {"symptoms": ["头晕"], "associated_symptoms": ["头晕"]},
    "犯迷糊": {"symptoms": ["嗜睡"], "associated_symptoms": ["嗜睡"]},
    "迷迷糊糊": {"symptoms": ["嗜睡"], "associated_symptoms": ["嗜睡"]},
    "特别渴": {"symptoms": ["极度口渴"]},
    "口干得厉害": {"symptoms": ["极度口渴"]},
    "冒冷汗": {"suspected_risk_signals": ["循环不稳信号"]},
    "脸色发白": {"suspected_risk_signals": ["循环不稳信号"]},
    "说话说不清": {"suspected_risk_signals": ["卒中风险"]},
    "一边没力气": {"suspected_risk_signals": ["卒中风险"]},
    "咽口水疼": {"symptoms": ["咽痛"], "associated_symptoms": ["吞咽疼痛"]},
    "吞口水疼": {"symptoms": ["咽痛"], "associated_symptoms": ["吞咽疼痛"]},
    "嗓子像刀割": {"symptoms": ["咽痛"], "severity": "中度"},
    "嗓子火辣辣": {"symptoms": ["咽痛"], "severity": "轻度"},
}


@dataclass
class FeatureExtractionBundle:
    merged_updates: dict[str, Any]
    display_updates: dict[str, Any]
    trace: dict[str, Any]


def merge_update_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if value is None:
            continue
        if isinstance(value, list):
            current = merged.get(key, [])
            if not isinstance(current, list):
                current = []
            cleaned = [item for item in value if isinstance(item, str) and item.strip()]
            merged[key] = unique_extend(current, cleaned)
        else:
            merged[key] = value
    return merged


def infer_fever_from_temperature(temperature: float) -> bool | None:
    if temperature >= 38.0:
        return True
    if temperature < 37.5:
        return False
    return None


def extract_regex_updates(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    import re

    updates: dict[str, Any] = {}
    regex_hits: dict[str, Any] = {}

    if contains_any(text, UNKNOWN_TEMPERATURE_PHRASES):
        updates["temperature_status"] = "未知"
        regex_hits["temperature_status"] = "未知"

    temperature_patterns = [
        r"(\d{2}(?:\.\d)?)\s*(?:c|°c|℃|度)",
        r"temperature(?:\s+is|\s*=|:)?\s*(\d{2}(?:\.\d)?)",
        r"体温(?:是|为|:)?\s*(\d{2}(?:\.\d)?)",
        r"(?:刚才测过|刚测|刚量|量了|测了)\s*(\d{2}(?:\.\d)?)",
    ]
    for pattern in temperature_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        temperature = float(match.group(1))
        if 30 <= temperature <= 45:
            updates["temperature"] = temperature
            updates["temperature_status"] = "已知"
            inferred_fever = infer_fever_from_temperature(temperature)
            if inferred_fever is not None:
                updates["fever_present"] = inferred_fever
            regex_hits["temperature"] = temperature
            break

    if "temperature" not in updates:
        if contains_any(text, NO_FEVER_PHRASES):
            updates["fever_present"] = False
            regex_hits["fever_present"] = "口述未发热"
        elif contains_any(text, FEVERISH_PHRASES):
            updates["fever_present"] = True
            regex_hits["fever_present"] = "口述发热"

    pain_patterns = [
        r"(\d{1,2})\s*/\s*10",
        r"pain(?:\s+score)?(?:\s+is|\s*=|:)?\s*(\d{1,2})",
        r"疼痛(?:评分)?(?:是|为|:)?\s*(\d{1,2})",
    ]
    for pattern in pain_patterns:
        match = re.search(pattern, text)
        if match:
            pain_score = int(match.group(1))
            if 0 <= pain_score <= 10:
                updates["pain_score"] = pain_score
                regex_hits["pain_score"] = pain_score
                break

    duration_patterns = [
        r"(\d+)\s*(hour|hours|day|days|week|weeks)",
        r"(\d+)\s*(?:个)?(小时|天|周)",
    ]
    for pattern in duration_patterns:
        match = re.search(pattern, text)
        if match:
            duration = f"{match.group(1)} {match.group(2)}"
            updates["duration"] = duration
            regex_hits["duration"] = duration
            break

    return updates, regex_hits


def extract_keyword_updates(text: str) -> tuple[dict[str, Any], list[str]]:
    updates: dict[str, Any] = {}
    keyword_hits: list[str] = []

    for phrase in ONSET_PHRASES:
        if phrase in text:
            updates["onset_time"] = phrase
            keyword_hits.append(f"起病时间:{phrase}")
            break

    if contains_any(text, ["severe", "very bad", "getting worse", "严重", "很严重", "加重"]):
        updates["severity"] = "重度"
        keyword_hits.append("严重程度:重度")
    elif contains_any(text, ["moderate", "中等"]):
        updates["severity"] = "中度"
        keyword_hits.append("严重程度:中度")
    elif contains_any(text, ["mild", "轻微", "轻度", "还行"]):
        updates["severity"] = "轻度"
        keyword_hits.append("严重程度:轻度")

    if contains_any(text, NEGATIVE_TRAUMA_PHRASES):
        updates["trauma_history"] = False
        keyword_hits.append("外伤史:否")
    elif contains_any(text, TRAUMA_KEYWORDS):
        updates["trauma_history"] = True
        keyword_hits.append("外伤史:是")

    symptoms_found: list[str] = []
    for keyword, normalized in SYMPTOM_KEYWORDS.items():
        if keyword in text:
            symptoms_found.append(normalized)
            keyword_hits.append(f"症状:{keyword}->{normalized}")

    if symptoms_found:
        normalized_symptoms = sorted(set(symptoms_found))
        updates["symptoms"] = normalized_symptoms
        associated_symptoms = [
            symptom
            for symptom in normalized_symptoms
            if symptom in {"呕吐", "出血", "嗜睡", "呼吸困难", "气短", "恶心", "头晕", "吞咽困难", "吞咽疼痛", "声音嘶哑"}
        ]
        if associated_symptoms:
            updates["associated_symptoms"] = associated_symptoms

    return updates, keyword_hits


def extract_lay_phrase_updates(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updates: dict[str, Any] = {}
    hits: list[dict[str, Any]] = []

    for phrase, mapped in LAY_PHRASE_MAPPINGS.items():
        if phrase not in text:
            continue
        hits.append({"phrase": phrase, "mapped_features": mapped})
        updates = merge_update_dicts(updates, mapped)

    return updates, hits


def translate_updates_for_display(updates: dict[str, Any]) -> dict[str, Any]:
    field_map = {
        "temperature_status": "体温状态",
        "temperature": "体温",
        "fever_present": "发热情况",
        "pain_score": "疼痛评分",
        "duration": "持续时间",
        "onset_time": "起病时间",
        "severity": "严重程度",
        "trauma_history": "外伤史",
        "symptoms": "识别症状",
        "associated_symptoms": "伴随症状",
        "suspected_risk_signals": "疑似风险信号",
    }
    display = {field_map.get(key, key): value for key, value in updates.items()}
    if "发热情况" in display:
        display["发热情况"] = "有发热" if display["发热情况"] is True else "未发热"
    if "外伤史" in display and isinstance(display["外伤史"], bool):
        display["外伤史"] = "有" if display["外伤史"] else "无"
    return display


def extract_features_from_message(message: str, context: SessionContext | None = None) -> FeatureExtractionBundle:
    text = message.lower()

    regex_updates, regex_hits = extract_regex_updates(text)
    keyword_updates, keyword_hits = extract_keyword_updates(text)
    lay_updates, lay_phrase_hits = extract_lay_phrase_updates(text)

    merged_updates = merge_update_dicts(regex_updates, keyword_updates)
    merged_updates = merge_update_dicts(merged_updates, lay_updates)

    llm_updates: dict[str, Any] = {}
    if context is not None:
        try:
            llm_updates = extract_updates_with_llm(message, context)
            merged_updates = merge_update_dicts(merged_updates, llm_updates)
        except Exception:
            llm_updates = {}

    trace = {
        "raw_text": message,
        "regex_hits": regex_hits,
        "keyword_hits": keyword_hits,
        "lay_phrase_hits": lay_phrase_hits,
        "llm_updates": llm_updates,
        "merged_updates": merged_updates,
    }

    return FeatureExtractionBundle(
        merged_updates=merged_updates,
        display_updates=translate_updates_for_display(merged_updates),
        trace=trace,
    )
