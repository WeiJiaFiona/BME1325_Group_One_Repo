from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import re
import uuid

from app_core.app.llm_adapter import generate_clinical_reply
from app_core.app.mode_user import start as run_user_mode
from app_core.app.planning.doctor_planner import build_doctor_plan
from app_core.app.planning.plan_validator import validate_plan
from app_core.app.rag.evidence_builder import build_evidence_package
from app_core.app.rag.protocol_retriever import retrieve_protocols
from app_core.app.schema import PayloadError, validate_encounter_start_payload
from app_core.doctor_rag.bridge import run_bridge
from app_core.clinical_kb.registry import registry_map


ALLOWED_RECEIVER_SYSTEMS = {"OUTPATIENT", "ICU", "WARD"}


@dataclass
class ApiError(Exception):
    message: str
    status_code: int = 400
    error_code: str = "INVALID_REQUEST"
    field_errors: Optional[List[Dict[str, str]]] = None

    def __str__(self) -> str:
        return self.message


_ENCOUNTERS: Dict[str, Dict[str, Any]] = {}
_HANDOFF_TICKETS: Dict[str, Dict[str, Any]] = {}
_USER_MODE_SESSION: Optional[Dict[str, Any]] = None

_SMALLTALK_PATTERNS = {
    "hi",
    "hello",
    "hey",
    "ok",
    "okay",
    "yes",
    "no",
    "你好",
    "在吗",
    "好的",
}

_SPELLING_FIXES = {
    "lowfeaver": "low fever",
    "feaver": "fever",
    "pheomonia": "pneumonia",
    "pheomoniabefore": "pneumonia before",
    "ihave": "i have",
    "ican'tmeasur": "i can't measure",
    "icantmeasure": "i can't measure",
    "ihanven'thadtheseinformation": "i have not had this information",
}

_SYMPTOM_KEYWORDS = {
    "chest pain": ["chest pain", "chest hurts", "胸痛", "胸口疼", "胸口很疼", "胸闷"],
    "shortness of breath": ["shortness of breath", "sob", "dyspnea", "呼吸困难", "喘不上气"],
    "fever": ["fever", "发烧", "低烧", "low fever"],
    "cough": ["cough", "咳嗽"],
    "nausea": ["nausea", "恶心"],
    "vomiting": ["vomit", "vomiting", "呕吐"],
    "dizziness": ["dizziness", "dizzy", "头晕"],
    "back pain": ["back pain", "low back pain", "腰痛", "背痛", "腰背痛", "下背痛"],
    "abdominal pain": ["abdominal pain", "belly pain", "腹痛", "肚子疼"],
    "labor": ["labor", "delivery", "giving birth", "分娩", "生小孩", "要生了", "宫缩", "羊水破了", "破水"],
    "allergic reaction": ["allergic reaction", "anaphylaxis", "hives", "throat tight", "过敏反应", "荨麻疹", "喉咙紧"],
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(text: str) -> str:
    t = text.strip()
    for wrong, right in _SPELLING_FIXES.items():
        t = re.sub(rf"\b{re.escape(wrong)}\b", right, t, flags=re.IGNORECASE)
    return t


def _is_smalltalk(text: str) -> bool:
    t = _normalize_text(text).strip().lower()
    if not t:
        return True
    if t in _SMALLTALK_PATTERNS:
        return True
    if re.fullmatch(r"(status|check queue|update)\??", t):
        return True
    return False


def _extract_vitals(text: str) -> Dict[str, float]:
    t = _normalize_text(text).lower()
    out: Dict[str, float] = {}
    spo2_match = re.search(r"(spo2|spo|氧饱和度|血氧|oxygen)[^\d]{0,8}(\d{2,3})", t)
    sbp_match = re.search(r"(sbp|收缩压|blood pressure|bp)[^\d]{0,8}(\d{2,3})", t)
    if spo2_match:
        out["spo2"] = float(spo2_match.group(2))
    if sbp_match:
        out["sbp"] = float(sbp_match.group(2))
    return out


def _extract_symptoms(text: str) -> List[str]:
    raw = _normalize_text(text).strip()
    if not raw or _is_smalltalk(raw):
        return []
    parts = [raw]
    for sep in [",", "，", ";", "；", "/", "|", " and "]:
        expanded: List[str] = []
        for p in parts:
            if sep in p:
                expanded.extend([x.strip() for x in p.split(sep) if x.strip()])
            else:
                expanded.append(p)
        parts = expanded

    inferred: List[str] = []
    lowered = raw.lower()
    for canonical, hints in _SYMPTOM_KEYWORDS.items():
        for h in hints:
            if h.lower() in lowered:
                inferred.append(canonical)
                break

    parts.extend(inferred)
    uniq: List[str] = []
    seen = set()
    for p in parts:
        if p.lower().startswith(("spo2", "sbp", "bp ")):
            continue
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def _extract_pain_score(text: str) -> Optional[int]:
    t = _normalize_text(text).lower()
    m = re.search(r"(pain|疼痛|痛感)[^\d]{0,8}(\d{1,2})", t)
    if not m:
        m = re.search(r"\b(\d{1,2})\s*/\s*10\b", t)
    if not m:
        return None
    v = int(m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1))
    if 0 <= v <= 10:
        return v
    return None


def _extract_duration(text: str) -> str:
    t = _normalize_text(text).lower()
    m = re.search(r"(\d+\s*(minute|minutes|min|hour|hours|day|days|小时|分钟|天))", t)
    if m:
        return m.group(1)
    m_cn = re.search(r"(昨天(上午|中午|下午|晚上)?|今天(上午|中午|下午|晚上)?|今早|昨晚|前天|刚刚|方才)", t)
    if m_cn:
        return m_cn.group(1)
    # Common colloquial CN time-of-day without an explicit day marker.
    # Examples: "从早上开始", "上午开始", "昨晚开始" (handled above), etc.
    m_cn2 = re.search(r"(从\s*)?(早上|上午|中午|下午|晚上)(开始|起)?", t)
    if m_cn2:
        return m_cn2.group(2)
    m2 = re.search(r"(since (this morning|yesterday|last night|today))", t)
    if m2:
        return m2.group(1)
    m3 = re.search(r"\b(yesterday morning|yesterday afternoon|yesterday evening|last night|this morning|today)\b", t)
    if m3:
        return m3.group(1)
    return ""


def _extract_binary_answer(text: str) -> Optional[bool]:
    t = _normalize_text(text).strip().lower()
    if re.fullmatch(r"(yes|y|yeah|yep|correct|是|是的|对|对的|有|嗯|好的)", t):
        return True
    if re.fullmatch(r"(no|n|nope|不是|不|没有|无|否|否认)", t):
        return False
    return None


def _apply_targeted_short_answer(session: Dict[str, Any], msg: str) -> None:
    target = str(_doctor_runtime(session).get("active_target", "")).strip()
    if not target:
        return
    data = _doctor_data(session)
    yn = _extract_binary_answer(msg)
    if target == "duration":
        duration = _extract_duration(msg)
        if duration:
            data["duration"] = duration
        return
    if target in data.get("red_flags", {}) and yn is not None:
        data["red_flags"][target] = yn
        return
    if target in {"water_broken", "vaginal_bleeding", "urge_to_push"} and yn is not None:
        data["obstetric"][target] = yn
        return
    if target == "contraction_interval":
        duration = _extract_duration(msg)
        if duration:
            data["obstetric"]["contraction_interval"] = duration


def _extract_red_flags(text: str) -> Dict[str, Optional[bool]]:
    t = _normalize_text(text).lower()
    out: Dict[str, Optional[bool]] = {
        "fever": None,
        "breathing_difficulty": None,
        "worsening_pain": None,
        "syncope": None,
        "radiating_pain": None,
    }
    if re.search(r"\b(no fever|without fever|afebrile|deny fever|denies fever)\b|不发烧|没发烧|否认发热|无发热", t):
        out["fever"] = False
    elif "fever" in t or "发烧" in t or "发热" in t:
        out["fever"] = True

    if re.search(
        r"\b(no breathing difficulty|breathing is okay|no sob|no shortness of breath|deny sob|denies sob)\b|呼吸还好|不喘|没有呼吸困难|无呼吸困难|否认呼吸困难|不气促",
        t,
    ):
        out["breathing_difficulty"] = False
    elif "shortness of breath" in t or "dyspnea" in t or "呼吸困难" in t or "喘不上" in t or "气促" in t:
        out["breathing_difficulty"] = True

    if re.search(r"\b(not worsening|stable pain|not worse)\b|没有加重|未加重|差不多", t):
        out["worsening_pain"] = False
    elif "worsening pain" in t or "pain getting worse" in t or "越来越疼" in t or "明显更痛" in t or "加重" in t:
        out["worsening_pain"] = True

    if re.search(r"没有晕厥|无晕厥|否认晕厥|没有晕倒|无晕倒|否认晕倒|deny syncope|denies syncope", t):
        out["syncope"] = False
    elif "faint" in t or "syncope" in t or "晕厥" in t or "晕倒" in t:
        out["syncope"] = True
    if re.search(r"没有放射|无放射|否认放射|不放射|deny radiating", t):
        out["radiating_pain"] = False
    elif "radiat" in t or "jaw" in t or "arm" in t or "放射痛" in t or "放射到" in t:
        out["radiating_pain"] = True
    return out


def _nurse_measured_vitals(chief_complaint: str, symptoms: List[str]) -> Dict[str, float]:
    text = f"{chief_complaint} {' '.join(symptoms)}".lower()
    spo2 = 97.0
    sbp = 122.0
    if any(k in text for k in ["shortness of breath", "呼吸困难", "chest pain", "胸痛", "喘"]):
        spo2 = 94.0
        sbp = 128.0
    if any(k in text for k in ["dizzy", "dizziness", "syncope", "头晕", "晕厥"]):
        sbp = 105.0
    if any(k in text for k in ["severe", "worst", "very bad", "剧烈"]):
        sbp = 90.0
        spo2 = min(spo2, 92.0)
    return {"spo2": spo2, "sbp": sbp}


def _role_label(agent_code: str) -> str:
    mapping = {
        "TRIAGE_NURSE": "triage_nurse",
        "CALLING_NURSE": "calling_nurse",
        "DOCTOR": "doctor",
        "BEDSIDE_NURSE": "bed_nurse",
        "SYSTEM": "system",
        "PATIENT": "patient",
    }
    return mapping.get(agent_code, "system")


def _agent_reply(
    agent: str,
    fallback: str,
    session: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> str:
    context = {
        "phase": session.get("phase"),
        "call_status": session.get("call_status"),
        "queue_position": session.get("queue_position"),
        "estimated_wait_minutes": session.get("estimated_wait_minutes"),
        "movement_suggestion": session.get("movement_suggestion"),
        "shared_memory": session.get("shared_memory", {}),
    }
    if extra:
        context.update(extra)
    if not use_llm:
        return fallback
    return generate_clinical_reply(agent=agent, context=context, fallback=fallback)


def _require_type(payload: Dict[str, Any], key: str, expected: type) -> Any:
    if key not in payload:
        raise ApiError(f"Missing required field: {key}", error_code="MISSING_FIELD")
    value = payload[key]
    if not isinstance(value, expected):
        raise ApiError(
            f"Invalid type for field `{key}`: expected {expected.__name__}",
            error_code="INVALID_TYPE",
        )
    return value


def _from_payload_error(exc: PayloadError) -> ApiError:
    field_errors: List[Dict[str, str]] = []
    if exc.field:
        field_errors.append(
            {
                "field": exc.field,
                "error_code": exc.error_code,
                "message": exc.message,
            }
        )
    return ApiError(
        message=exc.message,
        status_code=400,
        error_code=exc.error_code,
        field_errors=field_errors,
    )


def _infer_default_handoff_target(encounter: Dict[str, Any]) -> str:
    triage = encounter["triage"]
    if triage["acuity_ad"] in {"A", "B"}:
        return "ICU"
    if triage["acuity_ad"] == "C":
        return "WARD"
    return "OUTPATIENT"


def _doctor_topic_plan(session: Dict[str, Any]) -> List[str]:
    memory = session.get("shared_memory", {})
    chief = str(memory.get("chief_complaint", "")).lower()
    symptoms = " ".join(memory.get("symptoms", [])).lower()
    merged = chief + " " + symptoms
    if any(k in merged for k in ["labor", "delivery", "giving birth", "分娩", "生小孩", "要生", "宫缩", "羊水", "破水", "pregnan"]):
        return ["duration", "water_broken", "contraction_interval", "vaginal_bleeding", "urge_to_push"]
    base = ["duration", "worsening_pain"]
    if "chest" in merged or "胸" in merged:
        base.extend(["breathing_difficulty", "radiating_pain", "syncope"])
    elif "dyspnea" in merged or "呼吸" in merged or "sob" in merged:
        base.extend(["breathing_difficulty", "fever"])
    elif "fever" in merged or "发烧" in merged:
        base.extend(["fever", "breathing_difficulty"])
    else:
        base.extend(["fever", "breathing_difficulty"])
    ordered = []
    seen = set()
    for item in base:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _extract_json_fragment(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _llm_extract_doctor_fields(session: Dict[str, Any], msg: str) -> Dict[str, Any]:
    prompt = (
        "Extract clinical slots from patient free text. "
        "Return JSON only with keys: "
        "{\"duration\":string|null,"
        "\"pain_score\":number|null,"
        "\"fever\":true|false|null,"
        "\"breathing_difficulty\":true|false|null,"
        "\"worsening_pain\":true|false|null,"
        "\"syncope\":true|false|null,"
        "\"radiating_pain\":true|false|null,"
        "\"water_broken\":true|false|null,"
        "\"vaginal_bleeding\":true|false|null,"
        "\"urge_to_push\":true|false|null,"
        "\"contraction_interval\":string|null}.\n"
        f"Context={json.dumps(session.get('shared_memory', {}), ensure_ascii=False)}\n"
        f"Patient message={msg}"
    )
    raw = generate_clinical_reply("DOCTOR_EXTRACTOR", {"phase": "DOCTOR_CALLED"}, prompt)
    parsed = _extract_json_fragment(raw)
    return parsed if isinstance(parsed, dict) else {}


def _doctor_runtime(session: Dict[str, Any]) -> Dict[str, Any]:
    return session.setdefault(
        "doctor_runtime",
        {
            "active_target": "",
            "retry_counts": {},
            "assumptions": [],
        },
    )


def _apply_best_effort_target(session: Dict[str, Any], target: str) -> None:
    data = _doctor_data(session)
    runtime = _doctor_runtime(session)
    if target == "duration":
        data["duration"] = data.get("duration") or "unknown"
    elif target in data.get("red_flags", {}):
        # In best-effort mode, default unresolved risk booleans to False but keep trace.
        data["red_flags"][target] = False
    elif target in data.get("obstetric", {}):
        if target == "contraction_interval":
            data["obstetric"][target] = data["obstetric"].get(target) or "unknown"
        else:
            data["obstetric"][target] = False
    runtime["assumptions"].append(
        {
            "target": target,
            "mode": "best_effort_default",
            "ts": _utc_now_iso(),
        }
    )


def _doctor_data(session: Dict[str, Any]) -> Dict[str, Any]:
    return session.setdefault(
        "doctor_data",
        {
            "duration": "",
            "pain_score": None,
            "red_flags": {
                "fever": None,
                "breathing_difficulty": None,
                "worsening_pain": None,
                "syncope": None,
                "radiating_pain": None,
            },
            "obstetric": {
                "water_broken": None,
                "vaginal_bleeding": None,
                "urge_to_push": None,
                "contraction_interval": "",
            },
            "informative_turns": 0,
        },
    )


def _extract_obstetric_fields(text: str) -> Dict[str, Any]:
    t = _normalize_text(text).lower()
    out: Dict[str, Any] = {
        "water_broken": None,
        "vaginal_bleeding": None,
        "urge_to_push": None,
        "contraction_interval": "",
    }
    if re.search(r"羊水破|破水|water broke|water broken|water break", t):
        out["water_broken"] = True
    if re.search(r"没(有)?破水|未破水|no water break|water not broke", t):
        out["water_broken"] = False
    if re.search(r"阴道出血|见红|bleeding|vaginal bleeding", t):
        out["vaginal_bleeding"] = True
    if re.search(r"没有出血|未出血|no bleeding", t):
        out["vaginal_bleeding"] = False
    if re.search(r"想用力|有便意|push|bearing down", t):
        out["urge_to_push"] = True
    if re.search(r"不想用力|no urge to push", t):
        out["urge_to_push"] = False
    interval = re.search(r"(\d+\s*(分钟|min|minute|minutes).{0,6}(一次|一阵|per))", t)
    if interval:
        out["contraction_interval"] = interval.group(1)
    return out


def _update_doctor_data(session: Dict[str, Any], msg: str) -> None:
    data = _doctor_data(session)
    # "yes/no" can be clinically informative if it's answering the doctor's active slot question.
    runtime = _doctor_runtime(session)
    active_target = str(runtime.get("active_target", "")).strip()
    binary = _extract_binary_answer(msg)
    duration_hint = _extract_duration(msg)
    pain_hint = _extract_pain_score(msg)
    informative = (not _is_smalltalk(msg)) or (
        bool(active_target) and (binary is not None or bool(duration_hint) or pain_hint is not None)
    )
    if informative:
        data["informative_turns"] = int(data.get("informative_turns", 0)) + 1
    _apply_targeted_short_answer(session, msg)
    duration = duration_hint
    if duration and not data.get("duration"):
        data["duration"] = duration
    pain = pain_hint
    if pain is not None:
        data["pain_score"] = pain
    flags = _extract_red_flags(msg)
    for k, v in flags.items():
        if v is not None:
            data["red_flags"][k] = v
    ob = _extract_obstetric_fields(msg)
    for key in ["water_broken", "vaginal_bleeding", "urge_to_push"]:
        if isinstance(ob.get(key), bool):
            data["obstetric"][key] = ob[key]
    if isinstance(ob.get("contraction_interval"), str) and ob["contraction_interval"].strip():
        data["obstetric"]["contraction_interval"] = ob["contraction_interval"].strip()

    llm_slots = _llm_extract_doctor_fields(session, msg)
    if isinstance(llm_slots.get("duration"), str) and llm_slots["duration"].strip():
        data["duration"] = data.get("duration") or llm_slots["duration"].strip()
    if isinstance(llm_slots.get("pain_score"), (int, float)):
        score = int(llm_slots["pain_score"])
        if 0 <= score <= 10:
            data["pain_score"] = score
    for key in ["fever", "breathing_difficulty", "worsening_pain", "syncope", "radiating_pain"]:
        val = llm_slots.get(key)
        if isinstance(val, bool):
            data["red_flags"][key] = val
    for key in ["water_broken", "vaginal_bleeding", "urge_to_push"]:
        val = llm_slots.get(key)
        if isinstance(val, bool):
            data["obstetric"][key] = val
    if isinstance(llm_slots.get("contraction_interval"), str) and llm_slots["contraction_interval"].strip():
        data["obstetric"]["contraction_interval"] = llm_slots["contraction_interval"].strip()

    # Keep doctor findings in shared memory for cross-agent continuity.
    session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
    session["shared_memory"]["doctor_assessment"]["doctor_data"] = data
    _memory_touch(session)


def _doctor_missing_topics(session: Dict[str, Any]) -> List[str]:
    data = _doctor_data(session)
    targets = _doctor_topic_plan(session)
    miss: List[str] = []
    if not data.get("duration"):
        miss.append("duration")
    for k in targets:
        if k == "duration":
            continue
        if k in data.get("red_flags", {}):
            if data.get("red_flags", {}).get(k) is None:
                miss.append(k)
        elif k in data.get("obstetric", {}):
            val = data.get("obstetric", {}).get(k)
            if isinstance(val, str):
                if not val.strip():
                    miss.append(k)
            elif val is None:
                miss.append(k)
    return miss


def _doctor_ready_for_disposition(session: Dict[str, Any]) -> bool:
    data = _doctor_data(session)
    # Stage2 disposition readiness is further gated by protocol-aware logic.
    # Keep this base gate simple to avoid old generic topic plans forcing unrelated questions.
    return int(data.get("informative_turns", 0)) >= 2


def _doctor_filled_slots(session: Dict[str, Any]) -> Dict[str, Any]:
    data = _doctor_data(session)
    filled: Dict[str, Any] = {}
    if data.get("duration"):
        filled["duration"] = data.get("duration")
    if data.get("pain_score") is not None:
        filled["pain_score"] = data.get("pain_score")
    for k, v in data.get("red_flags", {}).items():
        if v is not None:
            filled[k] = v
    for k, v in data.get("obstetric", {}).items():
        if isinstance(v, str):
            if v.strip():
                filled[k] = v
        elif v is not None:
            filled[k] = v
    return filled


def _update_stage2_trace(
    session: Dict[str, Any],
    *,
    retrieval_result: Dict[str, Any],
    evidence: Dict[str, Any],
    validated: Dict[str, Any],
    plan_contract: Dict[str, Any],
    llm_plan_raw: str = "",
) -> None:
    assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
    assess["active_protocol_ids"] = [retrieval_result.get("primary_protocol_id")] + list(
        retrieval_result.get("secondary_protocol_ids", [])
    )
    assess["normalized_complaints"] = list(retrieval_result.get("normalized_complaints", []))
    assess["filled_slots"] = _doctor_filled_slots(session)
    assess["missing_critical_slots"] = list(plan_contract.get("missing_critical_slots", []))
    assess["plan_contract"] = plan_contract
    assess["safety_floor"] = {
        "urgency_floor": plan_contract.get("urgency_floor"),
        "disposition_floor": plan_contract.get("disposition_floor"),
    }
    asked_ids = list(assess.get("asked_question_ids", []))
    qid = str(plan_contract.get("primary_question", {}).get("id", "")).strip()
    if qid and qid not in asked_ids:
        asked_ids.append(qid)
    assess["asked_question_ids"] = asked_ids
    denied = list(assess.get("denied_red_flags", []))
    for key, val in _doctor_data(session).get("red_flags", {}).items():
        if val is False and key not in denied:
            denied.append(key)
    assess["denied_red_flags"] = denied
    trace = list(assess.get("planner_trace", []))
    trace.append(
        {
            "ts": _utc_now_iso(),
            "primary_protocol_id": retrieval_result.get("primary_protocol_id"),
            "secondary_protocol_ids": retrieval_result.get("secondary_protocol_ids", []),
            "retrieval_score": retrieval_result.get("retrieval_score", 0.0),
            "evidence_refs": evidence.get("evidence_refs", []),
            "llm_plan_raw": llm_plan_raw,
            "validator_result": validated.get("validator_result", "pass"),
            "warning_codes": validated.get("warning_codes", []),
            "override_applied": validated.get("override_applied", False),
            "fallback_used": bool(retrieval_result.get("fallback_used")) or bool(validated.get("fallback_used")),
        }
    )
    assess["planner_trace"] = trace[-60:]
    assess["updated_at"] = _utc_now_iso()
    _memory_touch(session)


def _ensure_user_session() -> Dict[str, Any]:
    global _USER_MODE_SESSION
    if _USER_MODE_SESSION is None:
        _USER_MODE_SESSION = {
            "patient_id": "Patient 1",
            "phase": "INTAKE",
            "current_agent": "TRIAGE_NURSE",
            "encounter_id": None,
            "handoff_ticket_id": None,
            "transcript": [],
            "pending_messages": [],
            "phase_changed": False,
            "memory_version": 0,
            "required_data": {
                "chief_complaint": "",
                "symptoms": [],
                "vitals": {},
            },
            "doctor_data": {
                "duration": "",
                "pain_score": None,
                "red_flags": {
                    "fever": None,
                    "breathing_difficulty": None,
                    "worsening_pain": None,
                    "syncope": None,
                    "radiating_pain": None,
                },
                "obstetric": {
                    "water_broken": None,
                    "vaginal_bleeding": None,
                    "urge_to_push": None,
                    "contraction_interval": "",
                },
                "informative_turns": 0,
            },
            "shared_memory": {
                "chief_complaint": "",
                "symptoms": [],
                "vitals": {},
                "triage": {},
                "doctor_assessment": {},
                "handoff": {},
            },
            "call_status": "WAITING_FOR_TRIAGE",
            "queue_position": 0,
            "estimated_wait_minutes": 0,
            "movement_suggestion": {
                "target_zone": "triage_waiting_area",
                "instruction": "Please wait near triage waiting area.",
            },
        }
    return _USER_MODE_SESSION


def _memory_touch(session: Dict[str, Any]) -> None:
    session["memory_version"] = int(session.get("memory_version", 0)) + 1


def _append_transcript(session: Dict[str, Any], agent: str, text: str) -> None:
    session["transcript"].append(
        {
            "timestamp": _utc_now_iso(),
            "role": _role_label(agent),
            "text": text,
        }
    )


def _enqueue_message(session: Dict[str, Any], role: str, text: str, event_type: str = "agent_prompt") -> None:
    item = {
        "role": role,
        "text": text,
        "ts": _utc_now_iso(),
        "event_type": event_type,
    }
    session.setdefault("pending_messages", []).append(item)


def _drain_pending_messages(session: Dict[str, Any]) -> List[Dict[str, str]]:
    raw = session.get("pending_messages", [])
    session["pending_messages"] = []
    out: List[Dict[str, str]] = []
    for msg in raw:
        out.append({"role": msg.get("role", "system"), "text": msg.get("text", "")})
    return out


def _remember_intake(session: Dict[str, Any], msg: str) -> None:
    req = session["required_data"]
    clean = _normalize_text(msg)
    if not req["chief_complaint"] and not _is_smalltalk(clean):
        req["chief_complaint"] = clean
    parsed_symptoms = _extract_symptoms(clean)
    if parsed_symptoms:
        req["symptoms"] = req["symptoms"] or parsed_symptoms
    elif req["chief_complaint"] and not req["symptoms"]:
        req["symptoms"] = _extract_symptoms(req["chief_complaint"])

    mem = session["shared_memory"]
    if req["chief_complaint"]:
        mem["chief_complaint"] = req["chief_complaint"]
    if req["symptoms"]:
        mem["symptoms"] = list(req["symptoms"])
    _memory_touch(session)


def _queue_metrics(session: Dict[str, Any]) -> Dict[str, int]:
    snap = queue_snapshot()
    before_me = 0
    if session["phase"] == "WAITING_CALL":
        before_me = max(0, int(snap.get("waiting_for_physician", 0)))
        enc_id = session.get("encounter_id")
        if enc_id and enc_id in _ENCOUNTERS:
            if _ENCOUNTERS[enc_id].get("final_state") == "WAITING_FOR_PHYSICIAN":
                before_me = max(0, before_me - 1)
    est_wait = before_me * 5
    if session.get("encounter_id") and session["encounter_id"] in _ENCOUNTERS:
        triage = _ENCOUNTERS[session["encounter_id"]]["triage"]
        if triage.get("level_1_4", 4) <= 2:
            est_wait = max(1, before_me * 2)
    return {"before_me": before_me, "estimated_wait_minutes": est_wait}


def _build_session_payload(session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_id": session["patient_id"],
        "phase": session["phase"],
        "current_agent": _role_label(session["current_agent"]),
        "call_status": session["call_status"],
        "queue_position": session["queue_position"],
        "estimated_wait_minutes": session["estimated_wait_minutes"],
        "encounter_id": session["encounter_id"],
        "handoff_ticket_id": session["handoff_ticket_id"],
        "movement_suggestion": session["movement_suggestion"],
        "memory_version": session.get("memory_version", 0),
    }


def _is_green_channel_encounter(encounter: Dict[str, Any]) -> bool:
    triage = encounter.get("triage", {}) if isinstance(encounter, dict) else {}
    hooks = set(triage.get("hooks", []) or [])
    if bool(triage.get("green_channel")):
        return True
    if triage.get("acuity_ad") in {"A", "B"}:
        return True
    if "abnormal_vitals" in hooks or "deterioration" in hooks:
        return True
    if encounter.get("final_state") == "UNDER_EVALUATION":
        return True
    return False


def _doctor_opening_from_memory(session: Dict[str, Any]) -> str:
    shared = session.get("shared_memory", {}) if isinstance(session.get("shared_memory"), dict) else {}
    chief = str(shared.get("chief_complaint", "")).strip()
    triage = shared.get("triage", {}) if isinstance(shared.get("triage"), dict) else {}
    acuity = str(triage.get("acuity_ad", "")).strip()
    if chief and acuity:
        return f"I reviewed your triage note: main complaint is {chief} (acuity {acuity}). What changed most since arrival?"
    if chief:
        return f"I reviewed your triage note: main complaint is {chief}. What changed most since arrival?"
    return "I reviewed your triage note. What changed most since arrival?"


def _doctor_disposition_summary(
    *,
    retrieval_result: Dict[str, Any],
    session: Dict[str, Any],
    target: str,
) -> str:
    protocol = str(retrieval_result.get("primary_protocol_id", "")).strip() or "general"
    data = _doctor_data(session)
    bits: List[str] = []
    if data.get("duration"):
        bits.append(f"onset: {data.get('duration')}")
    if data.get("pain_score") is not None:
        bits.append(f"pain_score: {data.get('pain_score')}/10")
    flags = data.get("red_flags", {})
    for key in ["worsening_pain", "breathing_difficulty", "syncope", "fever", "radiating_pain"]:
        val = flags.get(key)
        if val is True:
            bits.append(f"{key}: positive")
        elif val is False:
            bits.append(f"{key}: negative")
    core = "; ".join(bits[:4]) if bits else "limited but concerning data collected"
    return (
        f"Preliminary clinical impression: {protocol.replace('_', ' ')} pattern. "
        f"Key findings: {core}. "
        f"Current disposition plan: transfer to {target} for continued management."
    )


def _maybe_auto_progress(session: Dict[str, Any]) -> None:
    session["phase_changed"] = False

    if session["phase"] == "WAITING_CALL":
        queue = _queue_metrics(session)
        session["queue_position"] = queue["before_me"]
        session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
        if session["queue_position"] <= 0:
            session["phase_changed"] = True
            session["phase"] = "DOCTOR_CALLED"
            session["current_agent"] = "CALLING_NURSE"
            session["call_status"] = "CALLED"
            session["movement_suggestion"] = {
                "target_zone": "doctor_assessment_zone",
                "instruction": "Your number is called. Please go to doctor assessment zone now.",
            }
            _enqueue_message(
                session,
                "calling_nurse",
                f"{session['patient_id']}, your number is called. Please proceed to the doctor now.",
                event_type="number_called",
            )
            session["current_agent"] = "DOCTOR"
            doctor_line = _agent_reply(
                "DOCTOR",
                _doctor_opening_from_memory(session),
                session,
                use_llm=False,
            )
            _append_transcript(session, "DOCTOR", doctor_line)
            _enqueue_message(session, "doctor", doctor_line, event_type="agent_handoff")

    elif session["phase"] == "BED_NURSE_FLOW" and session.get("handoff_ticket_id"):
        session["phase_changed"] = True
        target_system = "ICU" if _ENCOUNTERS[session["encounter_id"]]["triage"]["acuity_ad"] in {"A", "B"} else "WARD"
        bed_number = f"{target_system}-BED-{str(session['patient_id']).split()[-1].zfill(2)}"
        complete = complete_handoff(
            {
                "handoff_ticket_id": session["handoff_ticket_id"],
                "receiver_system": target_system,
                "accepted": True,
                "receiver_bed": bed_number,
            }
        )
        session["phase"] = "DONE"
        session["call_status"] = "COMPLETED"
        session["current_agent"] = "BEDSIDE_NURSE"
        session["movement_suggestion"] = {
            "target_zone": "assigned_bed",
            "instruction": "Bed is arranged. Follow bedside nurse to assigned bed.",
        }
        session["shared_memory"]["handoff"] = complete
        _memory_touch(session)
        line = _agent_reply(
            "BEDSIDE_NURSE",
            (
                f"Bed arrangement done. Destination: {complete['final_disposition_state']}, "
                f"bed number {bed_number}, transfer latency {complete['transfer_latency_seconds']} seconds."
            ),
            session,
            extra={"handoff_result": complete},
            use_llm=False,
        )
        _append_transcript(session, "BEDSIDE_NURSE", line)
        _enqueue_message(session, "bed_nurse", line, event_type="agent_handoff")


def _doctor_next_question(topic: str, retry_count: int) -> str:
    direct = {
        "duration": "When exactly did this pain start?",
        "pain_score": "What is your current pain score from 0 to 10?",
        "fever": "Do you have fever now?",
        "breathing_difficulty": "Do you have breathing difficulty right now?",
        "worsening_pain": "Is the pain getting worse compared with yesterday?",
        "syncope": "Have you fainted or almost fainted?",
        "radiating_pain": "Does the pain spread to your arm, jaw, or back?",
        "water_broken": "Has your water broken?",
        "contraction_interval": "How often are the contractions now?",
        "vaginal_bleeding": "Do you have vaginal bleeding now?",
        "urge_to_push": "Do you feel an urge to push now?",
    }
    clearer = {
        "duration": "I still need the timeline: when exactly did it start (for example, yesterday morning or 2 days ago)?",
        "pain_score": "Please provide one number only: your pain score right now from 0 to 10.",
        "fever": "Please answer yes or no: do you currently have fever?",
        "breathing_difficulty": "Please answer yes or no: are you short of breath right now?",
        "worsening_pain": "Please answer yes or no: is it clearly worse than before?",
        "syncope": "Please answer yes or no: any fainting or near-fainting episode?",
        "radiating_pain": "Please answer yes or no: any pain spreading to arm, jaw, or back?",
        "water_broken": "Please answer yes or no: has your water broken already?",
        "contraction_interval": "Please tell me one number: about how many minutes between contractions now?",
        "vaginal_bleeding": "Please answer yes or no: any active vaginal bleeding right now?",
        "urge_to_push": "Please answer yes or no: do you feel strong urge to push now?",
    }
    if retry_count >= 1:
        return clearer.get(topic, "Please answer this point clearly in one short sentence?")
    return direct.get(topic, "Please clarify this symptom in one sentence?")


def _ensure_single_question(candidate: str, fallback: str) -> str:
    text = (candidate or "").strip()
    if not text:
        return fallback
    first_line = text.splitlines()[0].strip()
    pieces = re.split(r"(?<=[?？])", first_line)
    if pieces:
        first_piece = pieces[0].strip()
        if "?" in first_piece or "？" in first_piece:
            return first_piece
    if "?" in fallback or "？" in fallback:
        return fallback
    return f"{fallback.rstrip('.。!！')}?"


def _question_sig(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def _pick_alternative_slot(plan_contract: Dict[str, Any], current_slot: str) -> str:
    missing = [str(x).strip() for x in plan_contract.get("missing_critical_slots", []) if str(x).strip()]
    for slot in missing:
        if slot != current_slot:
            return slot
    return current_slot


def _doctor_min_turns(primary_protocol_id: str, urgency_proposed: str) -> int:
    base = {
        "trauma": 4,
        "chest_pain": 4,
        "dyspnea": 4,
        "stroke": 4,
        "headache": 4,
        "sepsis": 4,
        "labor": 3,
    }.get(primary_protocol_id, 3)
    if urgency_proposed in {"URGENT", "RESUS"}:
        return max(base, 4)
    return base


def _doctor_ready_stage2(
    session: Dict[str, Any],
    *,
    retrieval_result: Dict[str, Any],
    plan_contract: Dict[str, Any],
) -> bool:
    data = _doctor_data(session)
    informative_turns = int(data.get("informative_turns", 0))
    primary_protocol = str(retrieval_result.get("primary_protocol_id", "")).strip()
    urgency = str(plan_contract.get("urgency_proposed", "ROUTINE")).upper()
    missing = list(plan_contract.get("missing_critical_slots", []))
    min_turns = _doctor_min_turns(primary_protocol, urgency)
    if informative_turns < min_turns:
        return False
    # For urgent/resus protocols, require all critical slots to be addressed.
    if urgency in {"URGENT", "RESUS"}:
        return len(missing) == 0
    return len(missing) <= 1


def _build_doctor_followup_line(
    session: Dict[str, Any],
    *,
    plan_contract: Dict[str, Any],
    retrieval_result: Dict[str, Any],
    evidence: Dict[str, Any],
    patient_message: str,
) -> str:
    runtime = _doctor_runtime(session)
    primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
    q = plan_contract.get("primary_question", {}) if isinstance(plan_contract.get("primary_question"), dict) else {}
    slot = str(q.get("slot", "")).strip()
    fallback = str(q.get("text", "")).strip() or "When did the symptom start?"

    # If we are stuck asking the same slot repeatedly, move to another unresolved slot.
    retry_counts = runtime.setdefault("retry_counts", {})
    if slot and int(retry_counts.get(slot, 0)) >= 2:
        alt_slot = _pick_alternative_slot(plan_contract, slot)
        if alt_slot and alt_slot != slot:
            fallback = _doctor_next_question(alt_slot, 0)
            slot = alt_slot

    llm_draft = _agent_reply(
        "DOCTOR",
        fallback,
        session,
        extra={
            "mode": "adaptive_single_question",
            "primary_protocol_id": primary,
            "secondary_protocol_ids": retrieval_result.get("secondary_protocol_ids", []),
            "next_slot": slot,
            "missing_critical_slots": plan_contract.get("missing_critical_slots", []),
            "evidence_refs": (evidence.get("evidence_refs", []) or [])[:4],
            "patient_message": patient_message,
            "instruction": (
                "Ask exactly one concise follow-up question tailored to the current complaint. "
                "Do not ask multiple questions in one turn. Do not repeat a question already answered."
            ),
        },
        use_llm=True,
    )
    line = _ensure_single_question(llm_draft, fallback)

    # Anti-loop: avoid emitting an identical question twice in a row.
    prev = str(runtime.get("last_question_text", "")).strip()
    if prev and _question_sig(prev) == _question_sig(line):
        alt_slot = _pick_alternative_slot(plan_contract, slot)
        if alt_slot and alt_slot != slot:
            line = _ensure_single_question(_doctor_next_question(alt_slot, 0), fallback)
            slot = alt_slot
        else:
            line = _ensure_single_question(_doctor_next_question(slot or "duration", 1), fallback)

    runtime["last_question_text"] = line
    runtime["active_target"] = slot
    return line


def _is_imaging_question(text: str) -> bool:
    t = _normalize_text(text).lower()
    has_question = ("?" in t) or ("？" in t) or ("should" in t) or ("要不要" in t) or ("应该" in t) or ("需不需要" in t)
    img_kw = ["影像", "扫描", "ct", "mri", "x-ray", "xray", "拍片", "超声", "b超"]
    return has_question and any(k in t for k in img_kw)


def _imaging_fallback_recommendation(primary_protocol_id: str, language: str) -> str:
    if primary_protocol_id in {"stroke", "headache"}:
        return "根据目前症状，通常先做头颅 CT；若需要进一步评估可追加 MRI。"
    if primary_protocol_id == "trauma":
        return "外伤场景通常先做受伤部位 X 光，必要时补充 CT。"
    if primary_protocol_id == "abdominal_pain":
        return "腹痛场景通常先做腹部超声，必要时再做腹部 CT。"
    if primary_protocol_id == "chest_pain":
        return "胸痛场景通常先做心电图和胸片，必要时再评估胸部 CT。"
    if language == "zh":
        return "是否做影像要看风险分层；目前可先做基础评估，再决定 CT / MRI / 超声。"
    return "Imaging depends on risk stratification; we can start with basic assessment and then choose CT/MRI/ultrasound."


def user_mode_chat_turn(message: str) -> Dict[str, Any]:
    if not isinstance(message, str) or not message.strip():
        raise ApiError("`message` is required and must be non-empty")

    session = _ensure_user_session()
    msg = message.strip()
    clean_msg = _normalize_text(msg)
    _append_transcript(session, "PATIENT", msg)

    req = session["required_data"]
    req["vitals"].update(_extract_vitals(msg))
    pain = _extract_pain_score(msg)
    if pain is not None:
        req["vitals"]["pain_score"] = float(pain)
    if req.get("vitals"):
        session.setdefault("shared_memory", {})["vitals"] = dict(req["vitals"])
        _memory_touch(session)

    _maybe_auto_progress(session)

    if session["phase"] == "INTAKE":
        _remember_intake(session, msg)
        if not req["chief_complaint"]:
            ask = "Hi, I’m the triage nurse for intake. Before formal triage scoring, what brought you in today and how severe is it from 0 to 10?"
            session["current_agent"] = "TRIAGE_NURSE"
            session["call_status"] = "TRIAGE_INTAKE"
            _append_transcript(session, "TRIAGE_NURSE", ask)
            _enqueue_message(session, "triage_nurse", ask)
        else:
            session["phase"] = "CALL_NURSE_MEASURE"
            session["phase_changed"] = True
            session["current_agent"] = "CALLING_NURSE"
            session["call_status"] = "MEASURING_VITALS"
            session["movement_suggestion"] = {
                "target_zone": "vitals_station",
                "instruction": "Please proceed to calling nurse station for vital measurement.",
            }
            call_line = _agent_reply(
                "CALLING_NURSE",
                "I am the calling nurse. I will measure your vitals now and move you to triage immediately.",
                session,
                extra={"chief_complaint": req["chief_complaint"], "symptoms": req["symptoms"]},
                use_llm=False,
            )
            _append_transcript(session, "CALLING_NURSE", call_line)
            _enqueue_message(session, "calling_nurse", call_line, event_type="agent_handoff")

    if session["phase"] == "CALL_NURSE_MEASURE":
        measured = _nurse_measured_vitals(req.get("chief_complaint", ""), req.get("symptoms", []))
        for k, v in measured.items():
            req["vitals"].setdefault(k, v)
        session["shared_memory"]["vitals"] = dict(req["vitals"])
        _memory_touch(session)

        measure_note = (
            f"Vitals measured: SpO2 {int(req['vitals']['spo2'])}, SBP {int(req['vitals']['sbp'])}. "
            "Sending you to triage now."
        )
        _append_transcript(session, "CALLING_NURSE", measure_note)
        _enqueue_message(session, "calling_nurse", measure_note, event_type="measurement_completed")

        encounter = start_encounter(
            {
                "patient_id": session["patient_id"],
                "chief_complaint": req["chief_complaint"],
                "symptoms": req["symptoms"],
                "vitals": req["vitals"],
                "arrival_mode": "walk-in",
            }
        )
        session["encounter_id"] = encounter["encounter_id"]
        session["shared_memory"]["triage"] = encounter.get("triage", {})
        _memory_touch(session)

        triage_line = _agent_reply(
            "TRIAGE_NURSE",
            (
                f"Triage completed: acuity {encounter['triage']['acuity_ad']} "
                f"(CTAS {encounter['triage']['ctas_compat']})."
            ),
            session,
            extra={"triage": encounter.get("triage", {})},
            use_llm=False,
        )
        _append_transcript(session, "TRIAGE_NURSE", triage_line)
        _enqueue_message(session, "triage_nurse", triage_line, event_type="triage_completed")

        if _is_green_channel_encounter(encounter):
            session["phase"] = "DOCTOR_CALLED"
            session["phase_changed"] = True
            session["current_agent"] = "DOCTOR"
            session["queue_position"] = 0
            session["estimated_wait_minutes"] = 0
            session["call_status"] = "CALLED"
            session["movement_suggestion"] = {
                "target_zone": "doctor_assessment_zone",
                "instruction": "Urgent triage channel activated. Please move to doctor assessment zone now.",
            }
            doctor_line = _agent_reply(
                "DOCTOR",
                _doctor_opening_from_memory(session),
                session,
                extra={"triage": encounter.get("triage", {})},
                use_llm=False,
            )
            _append_transcript(session, "DOCTOR", doctor_line)
            _enqueue_message(session, "doctor", doctor_line, event_type="agent_handoff")
        else:
            session["phase"] = "WAITING_CALL"
            session["phase_changed"] = True
            session["current_agent"] = "CALLING_NURSE"
            queue = _queue_metrics(session)
            session["queue_position"] = queue["before_me"]
            session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
            session["call_status"] = "WAITING_CALL"
            session["movement_suggestion"] = {
                "target_zone": "triage_waiting_area",
                "instruction": "Please wait in waiting room until your number is called.",
            }
            if session["queue_position"] > 0:
                wait_line = _agent_reply(
                    "CALLING_NURSE",
                    (
                        f"You are in queue now. About {session['queue_position']} patients are before you, "
                        f"estimated wait {session['estimated_wait_minutes']} minutes."
                    ),
                    session,
                    use_llm=False,
                )
                _append_transcript(session, "CALLING_NURSE", wait_line)
                _enqueue_message(session, "calling_nurse", wait_line, event_type="queue_update")
            else:
                _maybe_auto_progress(session)

    elif session["phase"] == "WAITING_CALL":
        queue = _queue_metrics(session)
        session["queue_position"] = queue["before_me"]
        session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
        if session["queue_position"] > 0 and not _is_smalltalk(clean_msg):
            line = _agent_reply(
                "CALLING_NURSE",
                (
                    f"Please wait. {session['queue_position']} patients are before you, "
                    f"estimated {session['estimated_wait_minutes']} minutes."
                ),
                session,
                use_llm=False,
            )
            _append_transcript(session, "CALLING_NURSE", line)
            _enqueue_message(session, "calling_nurse", line, event_type="queue_update")

    elif session["phase"] == "DOCTOR_CALLED":
        session["call_status"] = "IN_CONSULTATION"
        session["current_agent"] = "DOCTOR"
        runtime = _doctor_runtime(session)
        expected_target = str(runtime.get("active_target", "")).strip()
        _update_doctor_data(session, msg)
        retrieval_result = retrieve_protocols(
            chief_complaint=str(session.get("shared_memory", {}).get("chief_complaint", "")),
            symptoms=list(session.get("shared_memory", {}).get("symptoms", []) or []),
            patient_message=msg,
            vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
        )
        evidence = build_evidence_package(session, retrieval_result)
        plan_contract = build_doctor_plan(session=session, patient_message=msg, retrieval_result=retrieval_result)
        validated = validate_plan(
            plan_contract=plan_contract,
            retrieval_result=retrieval_result,
            vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
        )
        plan_contract = dict(validated.get("plan_contract", {}))
        missing_critical = list(plan_contract.get("missing_critical_slots", []))
        next_target = str(plan_contract.get("primary_question", {}).get("slot", "")).strip()

        # Doctor KB RAG bridge: only affects phrasing/explanations/extraction (never decisions).
        bridge_result = None
        try:
            primary_pid = str(retrieval_result.get("primary_protocol_id", "")).strip()
            kb_reg = registry_map()
            complaint_id = primary_pid if primary_pid in kb_reg else ""
            if complaint_id and next_target:
                assess = session.get("shared_memory", {}).get("doctor_assessment", {}) if isinstance(session.get("shared_memory", {}), dict) else {}
                asked_ids = list((assess.get("asked_question_ids", []) or []))
                bridge_result = run_bridge(
                    complaint_id=complaint_id,
                    patient_text=msg,
                    language=str(plan_contract.get("language", "zh")).strip(),
                    next_slot=next_target,
                    filled_slots=_doctor_filled_slots(session),
                    asked_question_ids=asked_ids,
                )
                if getattr(bridge_result, "next_slot_echo", "") != next_target:
                    bridge_result = None
                else:
                    # Attach KB evidence refs so they appear in planner_trace.
                    if getattr(bridge_result, "evidence_refs", None):
                        evidence.setdefault("evidence_refs", [])
                        if isinstance(evidence.get("evidence_refs", None), list):
                            evidence["evidence_refs"].extend(list(bridge_result.evidence_refs))
        except Exception:
            bridge_result = None
        if next_target:
            runtime["active_target"] = next_target
            if next_target in missing_critical:
                retry_counts = runtime.setdefault("retry_counts", {})
                retry_counts[next_target] = int(retry_counts.get(next_target, 0)) + 1
                if retry_counts[next_target] > 2:
                    _apply_best_effort_target(session, next_target)
                    # Rebuild plan after best-effort defaulting.
                    plan_contract = build_doctor_plan(session=session, patient_message=msg, retrieval_result=retrieval_result)
                    validated = validate_plan(
                        plan_contract=plan_contract,
                        retrieval_result=retrieval_result,
                        vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
                    )
                    plan_contract = dict(validated.get("plan_contract", {}))
                    missing_critical = list(plan_contract.get("missing_critical_slots", []))
                    runtime["active_target"] = str(plan_contract.get("primary_question", {}).get("slot", "")).strip()
            elif expected_target == next_target:
                runtime.setdefault("retry_counts", {})[next_target] = 0

        _update_stage2_trace(
            session,
            retrieval_result=retrieval_result,
            evidence=evidence,
            validated=validated,
            plan_contract=plan_contract,
        )

        old_ready = _doctor_ready_for_disposition(session)
        if retrieval_result.get("fallback_used", False):
            # If we failed to retrieve a matching protocol, we must be MORE conservative,
            # otherwise a generic "what do you mean" turn can prematurely trigger WARD/ICU handoff.
            data = _doctor_data(session)
            informative_turns = int(data.get("informative_turns", 0))
            answered_flags = sum(
                1
                for v in (data.get("red_flags", {}) or {}).values()
                if isinstance(v, bool)
            )
            has_duration = bool(str(data.get("duration", "")).strip())
            ready_for_disposition = bool(old_ready and informative_turns >= 4 and has_duration and answered_flags >= 2)
        else:
            ready_for_disposition = bool(
                old_ready
                and _doctor_ready_stage2(
                    session,
                    retrieval_result=retrieval_result,
                    plan_contract=plan_contract,
                )
            )

        if not ready_for_disposition:
            if bridge_result is not None and getattr(bridge_result, "patient_explanation", ""):
                imaging_line = str(bridge_result.patient_explanation).strip()
                _append_transcript(session, "DOCTOR", imaging_line)
                _enqueue_message(session, "doctor", imaging_line, event_type="doctor_answer")
            elif _is_imaging_question(msg):
                # Legacy fallback when KB not available.
                primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
                lang = str(plan_contract.get("language", "zh")).strip()
                imaging_fallback = _imaging_fallback_recommendation(primary, lang)
                imaging_line = _agent_reply(
                    "DOCTOR",
                    imaging_fallback,
                    session,
                    extra={"mode": "patient_question_answer", "primary_protocol_id": primary, "patient_message": msg},
                    use_llm=True,
                )
                _append_transcript(session, "DOCTOR", imaging_line)
                _enqueue_message(session, "doctor", imaging_line, event_type="doctor_answer")

            if bridge_result is not None and getattr(bridge_result, "rendered_question", ""):
                line = _ensure_single_question(str(bridge_result.rendered_question), "When did it start?")
            else:
                line = _build_doctor_followup_line(
                    session,
                    plan_contract=plan_contract,
                    retrieval_result=retrieval_result,
                    evidence=evidence,
                    patient_message=msg,
                )
            _append_transcript(session, "DOCTOR", line)
            _enqueue_message(session, "doctor", line, event_type="doctor_followup")
        else:
            encounter = _ENCOUNTERS.get(session["encounter_id"], {})
            triage = encounter.get("triage", {})
            acuity = triage.get("acuity_ad", "C")
            assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
            assess["doctor_data"] = _doctor_data(session)
            assess["assumptions"] = _doctor_runtime(session).get("assumptions", [])
            assess["updated_at"] = _utc_now_iso()
            _memory_touch(session)

            if acuity in {"A", "B", "C"}:
                target = "ICU" if acuity in {"A", "B"} else "WARD"
                ticket = request_handoff(
                    {
                        "encounter_id": session["encounter_id"],
                        "target_system": target,
                        "reason": "doctor disposition after assessment",
                    }
                )
                session["handoff_ticket_id"] = ticket["handoff_ticket_id"]
                session["phase"] = "BED_NURSE_FLOW"
                session["phase_changed"] = True
                session["current_agent"] = "BEDSIDE_NURSE"
                session["movement_suggestion"] = {
                    "target_zone": "bedside_transfer_zone",
                    "instruction": f"Proceed to bedside transfer area for {target} arrangement.",
                }
                line = _agent_reply(
                    "DOCTOR",
                    _doctor_disposition_summary(
                        retrieval_result=retrieval_result,
                        session=session,
                        target=target,
                    ),
                    session,
                    extra={
                        "target_system": target,
                        "patient_message": msg,
                        "doctor_data": _doctor_data(session),
                        "retrieval_result": retrieval_result,
                    },
                    use_llm=False,
                )
                _append_transcript(session, "DOCTOR", line)
                _enqueue_message(session, "doctor", line, event_type="doctor_disposition")
                _maybe_auto_progress(session)
            else:
                session["phase"] = "DONE"
                session["phase_changed"] = True
                session["current_agent"] = "DOCTOR"
                session["call_status"] = "COMPLETED"
                session["movement_suggestion"] = {
                    "target_zone": "outpatient_exit",
                    "instruction": "You can proceed to outpatient follow-up.",
                }
                line = _agent_reply(
                    "DOCTOR",
                    "Assessment complete. Follow outpatient pathway for next management.",
                    session,
                    extra={"patient_message": msg},
                    use_llm=False,
                )
                _append_transcript(session, "DOCTOR", line)
                _enqueue_message(session, "doctor", line, event_type="doctor_disposition")

    elif session["phase"] == "BED_NURSE_FLOW":
        _maybe_auto_progress(session)

    else:
        if not _is_smalltalk(clean_msg):
            line = _agent_reply(
                "SYSTEM",
                "Current encounter is completed. Start a new session if needed.",
                session,
                use_llm=False,
            )
            _append_transcript(session, "SYSTEM", line)
            _enqueue_message(session, "system", line, event_type="session_completed")

    _maybe_auto_progress(session)
    pending_messages = list(session.get("pending_messages", []))
    messages = _drain_pending_messages(session)

    return {
        "session": _build_session_payload(session),
        "messages": messages,
        "pending_messages": pending_messages,
        "phase_changed": bool(session.get("phase_changed", False)),
        "transcript_tail": session["transcript"][-20:],
    }


def user_mode_session_status() -> Dict[str, Any]:
    session = _ensure_user_session()
    _maybe_auto_progress(session)
    pending_messages = list(session.get("pending_messages", []))
    messages = _drain_pending_messages(session)
    return {
        "session": _build_session_payload(session),
        "messages": messages,
        "pending_messages": pending_messages,
        "phase_changed": bool(session.get("phase_changed", False)),
        "transcript_tail": session["transcript"][-20:],
    }


def reset_user_mode_session() -> Dict[str, Any]:
    global _USER_MODE_SESSION
    _USER_MODE_SESSION = None
    session = _ensure_user_session()
    return {
        "session": _build_session_payload(session),
        "messages": [],
        "pending_messages": [],
        "phase_changed": False,
        "transcript_tail": [],
    }


def start_encounter(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cleaned = validate_encounter_start_payload(payload)
    except PayloadError as exc:
        raise _from_payload_error(exc) from exc

    patient_id = str(cleaned.get("patient_id", "")).strip() or f"patient-{uuid.uuid4().hex[:6]}"
    user_payload = {
        "patient_id": patient_id,
        "chief_complaint": cleaned["chief_complaint"],
        "symptoms": cleaned.get("symptoms", []),
        "vitals": cleaned["vitals"],
        "arrival_mode": cleaned["arrival_mode"],
    }
    result = run_user_mode(user_payload)
    if "error_code" in result:
        raise ApiError(
            result.get("message", "Encounter start failed"),
            status_code=400,
            error_code=str(result.get("error_code", "INVALID_REQUEST")),
            field_errors=result.get("field_errors") or [],
        )

    encounter_id = f"enc-{uuid.uuid4().hex[:10]}"
    created_at = _utc_now_iso()
    encounter = {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "triage": result["triage"],
        "state_trace": result["state_trace"],
        "final_state": result["final_state"],
        "created_at": created_at,
        "updated_at": created_at,
        "handoff_status": "NONE",
    }
    _ENCOUNTERS[encounter_id] = encounter

    return {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "triage": result["triage"],
        "state_trace": result["state_trace"],
        "final_state": result["final_state"],
        "recommended_handoff_target": _infer_default_handoff_target(encounter),
        "status": "STARTED",
    }


def request_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    encounter_id = _require_type(payload, "encounter_id", str)
    reason = _require_type(payload, "reason", str).strip()
    target_system = _require_type(payload, "target_system", str).strip().upper()

    if target_system not in ALLOWED_RECEIVER_SYSTEMS:
        allowed = ", ".join(sorted(ALLOWED_RECEIVER_SYSTEMS))
        raise ApiError(f"Invalid `target_system`; allowed values: {allowed}")
    if encounter_id not in _ENCOUNTERS:
        raise ApiError(f"Unknown encounter_id: {encounter_id}", status_code=404)
    if not reason:
        raise ApiError("`reason` cannot be empty")

    encounter = _ENCOUNTERS[encounter_id]
    ticket_id = f"hdt-{uuid.uuid4().hex[:10]}"
    created_at = _utc_now_iso()
    ticket = {
        "handoff_ticket_id": ticket_id,
        "encounter_id": encounter_id,
        "patient_id": encounter["patient_id"],
        "status": "REQUESTED",
        "target_system": target_system,
        "reason": reason,
        "created_at": created_at,
        "accepted_at": None,
        "receiver_bed": None,
        "receiver_system": None,
    }
    _HANDOFF_TICKETS[ticket_id] = ticket

    encounter["handoff_status"] = "REQUESTED"
    encounter["updated_at"] = created_at
    encounter["last_handoff_ticket_id"] = ticket_id

    return {
        "handoff_ticket_id": ticket_id,
        "status": "REQUESTED",
        "event_type": f"ED_PATIENT_READY_FOR_{target_system}",
        "reason": reason,
    }


def complete_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    ticket_id = _require_type(payload, "handoff_ticket_id", str)
    receiver_system = _require_type(payload, "receiver_system", str).strip().upper()
    accepted = _require_type(payload, "accepted", bool)
    accepted_at = str(payload.get("accepted_at", _utc_now_iso()))
    receiver_bed = payload.get("receiver_bed")
    if receiver_bed is not None and not isinstance(receiver_bed, str):
        raise ApiError("`receiver_bed` must be a string when provided")

    if receiver_system not in ALLOWED_RECEIVER_SYSTEMS:
        allowed = ", ".join(sorted(ALLOWED_RECEIVER_SYSTEMS))
        raise ApiError(f"Invalid `receiver_system`; allowed values: {allowed}")
    if ticket_id not in _HANDOFF_TICKETS:
        raise ApiError(f"Unknown handoff_ticket_id: {ticket_id}", status_code=404)

    ticket = _HANDOFF_TICKETS[ticket_id]
    if ticket["status"] == "COMPLETED":
        raise ApiError(f"Handoff ticket already completed: {ticket_id}")

    if receiver_system != ticket["target_system"]:
        raise ApiError(
            f"receiver_system mismatch: expected {ticket['target_system']}, got {receiver_system}"
        )

    now_ts = _utc_now_iso()
    ticket["receiver_system"] = receiver_system
    ticket["accepted_at"] = accepted_at
    ticket["receiver_bed"] = receiver_bed
    ticket["status"] = "COMPLETED" if accepted else "REJECTED"

    encounter = _ENCOUNTERS[ticket["encounter_id"]]
    encounter["updated_at"] = now_ts
    if accepted:
        encounter["handoff_status"] = "COMPLETED"
        encounter["final_state"] = receiver_system
    else:
        encounter["handoff_status"] = "REJECTED"
        encounter["final_state"] = "AWAITING_DISPOSITION"

    req_ts = _parse_iso(ticket["created_at"])
    done_ts = _parse_iso(accepted_at)
    latency = max(0, int((done_ts - req_ts).total_seconds()))

    return {
        "handoff_ticket_id": ticket_id,
        "status": ticket["status"],
        "final_disposition_state": encounter["final_state"],
        "transfer_latency_seconds": latency,
        "receiver_system": receiver_system,
        "receiver_bed": receiver_bed,
    }


def queue_snapshot() -> Dict[str, Any]:
    waiting_for_physician = 0
    under_evaluation = 0
    high_acuity_waiting = 0
    awaiting_handoff = 0
    active_encounters = 0

    for enc in _ENCOUNTERS.values():
        if enc["final_state"] not in {"OUTPATIENT", "ICU", "WARD", "LEAVE_ED"}:
            active_encounters += 1
        if enc["final_state"] == "WAITING_FOR_PHYSICIAN":
            waiting_for_physician += 1
            if enc["triage"]["level_1_4"] <= 2:
                high_acuity_waiting += 1
        if enc["final_state"] == "UNDER_EVALUATION":
            under_evaluation += 1
        if enc.get("handoff_status") == "REQUESTED":
            awaiting_handoff += 1

    requested = sum(1 for t in _HANDOFF_TICKETS.values() if t["status"] == "REQUESTED")
    completed = sum(1 for t in _HANDOFF_TICKETS.values() if t["status"] == "COMPLETED")
    rejected = sum(1 for t in _HANDOFF_TICKETS.values() if t["status"] == "REJECTED")

    return {
        "total_encounters": len(_ENCOUNTERS),
        "active_encounters": active_encounters,
        "waiting_for_physician": waiting_for_physician,
        "under_evaluation": under_evaluation,
        "high_acuity_waiting": high_acuity_waiting,
        "awaiting_handoff": awaiting_handoff,
        "handoff": {
            "requested": requested,
            "completed": completed,
            "rejected": rejected,
            "total_tickets": len(_HANDOFF_TICKETS),
        },
    }


def reset_runtime_state() -> None:
    _ENCOUNTERS.clear()
    _HANDOFF_TICKETS.clear()
    global _USER_MODE_SESSION
    _USER_MODE_SESSION = None
