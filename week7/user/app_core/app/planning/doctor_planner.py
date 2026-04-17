from __future__ import annotations

from typing import Any, Dict, List

from app_core.app.planning.fallback_templates import fallback_patient_utterance, fallback_question


def detect_language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def _slot_value(slot: str, doctor_data: Dict[str, Any]) -> Any:
    if slot == "duration":
        return doctor_data.get("duration", "")
    if slot == "pain_score":
        return doctor_data.get("pain_score", None)
    if slot in doctor_data.get("red_flags", {}):
        return doctor_data["red_flags"].get(slot)
    if slot in doctor_data.get("obstetric", {}):
        return doctor_data["obstetric"].get(slot)
    return None


def _pick_next_question(protocol_doc: Dict[str, Any], doctor_data: Dict[str, Any], language: str) -> Dict[str, Any]:
    asked_ids = set(
        str(x).strip()
        for x in (
            (doctor_data.get("meta", {}) or {}).get("asked_question_ids", [])
            if isinstance(doctor_data.get("meta", {}), dict)
            else []
        )
    )
    questions = sorted(protocol_doc.get("questions", []), key=lambda q: int(q.get("priority", 0)), reverse=True)
    first_missing: Dict[str, Any] = {}
    for q in questions:
        slot = str(q.get("slot", "")).strip()
        val = _slot_value(slot, doctor_data)
        missing = (val is None) or (isinstance(val, str) and not val.strip())
        if missing:
            candidate = {
                "id": str(q.get("question_id", "unknown")),
                "text": str(q.get(language, q.get("en", "")) or fallback_question(slot, language)),
                "slot": slot,
                "answer_type": str(q.get("answer_type", "text")),
            }
            if not first_missing:
                first_missing = candidate
            if candidate["id"] not in asked_ids:
                return candidate

    if first_missing:
        return first_missing

    slot = str(protocol_doc.get("required_slots", ["duration"])[0]) if protocol_doc.get("required_slots") else "duration"
    return {
        "id": "fallback_q",
        "text": fallback_question(slot, language),
        "slot": slot,
        "answer_type": "text",
    }


def build_doctor_plan(
    *,
    session: Dict[str, Any],
    patient_message: str,
    retrieval_result: Dict[str, Any],
) -> Dict[str, Any]:
    language = detect_language(patient_message)
    doctor_data = dict(session.get("doctor_data", {}))
    assess = (
        session.get("shared_memory", {}).get("doctor_assessment", {})
        if isinstance(session.get("shared_memory", {}), dict)
        else {}
    )
    # Planner consumes asked IDs only to avoid unnecessary repeats.
    doctor_data["meta"] = {"asked_question_ids": list(assess.get("asked_question_ids", []))}
    protocol_doc = retrieval_result.get("protocol_doc", {})
    primary_question = _pick_next_question(protocol_doc, doctor_data, language)

    missing_slots: List[str] = []
    for slot in protocol_doc.get("required_slots", []):
        val = _slot_value(slot, doctor_data)
        if (val is None) or (isinstance(val, str) and not val.strip()):
            missing_slots.append(slot)

    shared = session.get("shared_memory", {}) if isinstance(session.get("shared_memory"), dict) else {}
    vitals = shared.get("vitals", {}) if isinstance(shared.get("vitals"), dict) else {}
    spo2 = float(vitals.get("spo2", 97) or 97)
    sbp = float(vitals.get("sbp", 120) or 120)

    urgency_floor = "ROUTINE"
    disposition_floor = "OUTPATIENT"

    # Generic physiological floor.
    if spo2 < 90 or sbp < 90:
        urgency_floor = "RESUS"
        disposition_floor = "ICU"
    elif spo2 < 94 or sbp < 100:
        urgency_floor = "URGENT"
        disposition_floor = "OBSERVE"

    # Protocol-rule floor (v1.1): parse simple conditions such as spo2<90 / sbp<90 / complaint:stroke.
    normalized = set(retrieval_result.get("normalized_complaints", []))
    normalized.add(str(retrieval_result.get("primary_protocol_id", "")).strip())
    red_flags = doctor_data.get("red_flags", {})
    obstetric = doctor_data.get("obstetric", {})

    def _cond_true(cond: str) -> bool:
        c = str(cond).strip().lower()
        if c.startswith("spo2<"):
            try:
                return spo2 < float(c.split("<", 1)[1])
            except Exception:
                return False
        if c.startswith("sbp<"):
            try:
                return sbp < float(c.split("<", 1)[1])
            except Exception:
                return False
        if c.startswith("complaint:"):
            return c.split(":", 1)[1].strip() in normalized
        if c.startswith("red_flag:"):
            key = c.split(":", 1)[1].strip()
            if key in red_flags:
                return bool(red_flags.get(key))
            if key in obstetric:
                return bool(obstetric.get(key))
            return False
        return False

    level_u = {"ROUTINE": 0, "URGENT": 1, "RESUS": 2}
    level_d = {"OUTPATIENT": 0, "OBSERVE": 1, "WARD": 2, "ICU": 3}
    for rule in protocol_doc.get("urgency_rules", []):
        conds = [str(x) for x in rule.get("if_all", [])]
        if conds and all(_cond_true(x) for x in conds):
            ru = str(rule.get("urgency_floor", urgency_floor)).upper()
            rd = str(rule.get("disposition_floor", disposition_floor)).upper()
            if level_u.get(ru, 0) > level_u.get(urgency_floor, 0):
                urgency_floor = ru
            if level_d.get(rd, 0) > level_d.get(disposition_floor, 0):
                disposition_floor = rd

    return {
        "primary_question": primary_question,
        "patient_utterance": fallback_patient_utterance(language),
        "risk_flags": retrieval_result.get("red_flag_union", []),
        "urgency_floor": urgency_floor,
        "urgency_proposed": urgency_floor,
        "disposition_floor": disposition_floor,
        "disposition_proposed": disposition_floor,
        "missing_critical_slots": missing_slots,
        "evidence_refs": retrieval_result.get("evidence_refs", []),
        "language": language,
    }
