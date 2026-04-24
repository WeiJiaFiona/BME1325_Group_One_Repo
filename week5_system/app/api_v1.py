from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
import re

from week5_system.app.llm_adapter import generate_clinical_reply
from week5_system.app.mode_user import start as run_user_mode
from week5_system.app.schema import PayloadError, validate_encounter_start_payload


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
    "abdominal pain": ["abdominal pain", "belly pain", "腹痛", "肚子疼"],
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _agent_reply(agent: str, fallback: str, session: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> str:
    context = {
        "phase": session.get("phase"),
        "call_status": session.get("call_status"),
        "queue_position": session.get("queue_position"),
        "estimated_wait_minutes": session.get("estimated_wait_minutes"),
        "movement_suggestion": session.get("movement_suggestion"),
    }
    if extra:
        context.update(extra)
    return generate_clinical_reply(agent=agent, context=context, fallback=fallback)


def _infer_default_handoff_target(encounter: Dict[str, Any]) -> str:
    triage = encounter["triage"]
    if triage["acuity_ad"] in {"A", "B"}:
        return "ICU"
    if triage["acuity_ad"] == "C":
        return "WARD"
    return "OUTPATIENT"


def _role_label(agent_code: str) -> str:
    mapping = {
        "TRIAGE_NURSE": "triage_nurse",
        "DOCTOR": "doctor",
        "BEDSIDE_NURSE": "bed_nurse",
        "SYSTEM": "system",
        "PATIENT": "patient",
    }
    return mapping.get(agent_code, "system")


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
    m2 = re.search(r"(since (this morning|yesterday|last night|today))", t)
    if m2:
        return m2.group(1)
    return ""


def _extract_red_flags(text: str) -> Dict[str, Optional[bool]]:
    t = _normalize_text(text).lower()
    out: Dict[str, Optional[bool]] = {"fever": None, "breathing_difficulty": None, "worsening_pain": None}
    if re.search(r"\b(no fever|without fever|afebrile)\b|不发烧|没发烧|低烧", t):
        out["fever"] = False
    elif "fever" in t or "发烧" in t:
        out["fever"] = True

    if re.search(r"\b(no breathing difficulty|breathing is okay|no sob)\b|呼吸还好|不喘", t):
        out["breathing_difficulty"] = False
    elif "shortness of breath" in t or "dyspnea" in t or "呼吸困难" in t:
        out["breathing_difficulty"] = True

    if re.search(r"\b(not worsening|stable pain)\b|没有加重|未加重", t):
        out["worsening_pain"] = False
    elif "worsening pain" in t or "pain getting worse" in t or "越来越疼" in t or "加重" in t:
        out["worsening_pain"] = True
    return out


def _cannot_measure_vitals(text: str) -> bool:
    t = _normalize_text(text).lower()
    compact = re.sub(r"[^a-z]", "", t)
    if any(k in t for k in ["can't measure", "cannot measure", "unable to measure", "can't get spo2", "no device"]):
        return True
    if "cantmeasure" in compact or "cannotmeasure" in compact:
        return True
    if "noequipment" in compact:
        return True
    return False


def _nurse_measured_vitals(chief_complaint: str, symptoms: List[str]) -> Dict[str, float]:
    text = f"{chief_complaint} {' '.join(symptoms)}".lower()
    spo2 = 97.0
    sbp = 122.0
    if any(k in text for k in ["shortness of breath", "呼吸困难", "chest pain", "胸痛", "喘"]):
        spo2 = 94.0
        sbp = 128.0
    if any(k in text for k in ["dizzy", "dizziness", "syncope", "头晕"]):
        sbp = 110.0
    if any(k in text for k in ["severe", "worst", "very bad", "剧烈"]):
        sbp = 135.0
    return {"spo2": spo2, "sbp": sbp}


def _next_intake_question(missing: List[str]) -> str:
    if "chief_complaint" in missing:
        return "Please briefly describe what brought you to the ED today."
    if "symptoms" in missing:
        return "Please share your key symptoms (for example chest pain, shortness of breath, nausea)."
    if "spo2" in missing and "sbp" in missing:
        return "Please provide both SpO2 and SBP if available, for example `spo2 95 sbp 120`. If you cannot measure them, tell me and we will check them in triage."
    if "spo2" in missing:
        return "Please provide your SpO2 (blood oxygen), for example `spo2 95`. If unavailable, tell me and we will measure it for you."
    return "Please provide your systolic blood pressure (SBP), for example `sbp 120`. If unavailable, tell me and we will measure it for you."


def _doctor_data(session: Dict[str, Any]) -> Dict[str, Any]:
    data = session.setdefault(
        "doctor_data",
        {
            "duration": "",
            "pain_score": None,
            "red_flags": {"fever": None, "breathing_difficulty": None, "worsening_pain": None},
            "informative_turns": 0,
        },
    )
    return data


def _update_doctor_data(session: Dict[str, Any], msg: str) -> None:
    data = _doctor_data(session)
    informative = not _is_smalltalk(msg)
    if informative:
        data["informative_turns"] = int(data.get("informative_turns", 0)) + 1
    duration = _extract_duration(msg)
    if duration and not data.get("duration"):
        data["duration"] = duration
    pain = _extract_pain_score(msg)
    if pain is not None:
        data["pain_score"] = pain
    flags = _extract_red_flags(msg)
    for k, v in flags.items():
        if v is not None:
            data["red_flags"][k] = v


def _doctor_missing_topics(session: Dict[str, Any]) -> List[str]:
    data = _doctor_data(session)
    miss: List[str] = []
    if not data.get("duration"):
        miss.append("duration")
    for k, v in data.get("red_flags", {}).items():
        if v is None:
            miss.append(k)
    return miss


def _doctor_ready_for_disposition(session: Dict[str, Any]) -> bool:
    data = _doctor_data(session)
    missing = _doctor_missing_topics(session)
    return int(data.get("informative_turns", 0)) >= 2 and len(missing) <= 1


def _ensure_user_session() -> Dict[str, Any]:
    global _USER_MODE_SESSION
    if _USER_MODE_SESSION is None:
        _USER_MODE_SESSION = {
            "patient_id": "Patient 1",
            "phase": "INTAKE",
            "current_agent": "TRIAGE_NURSE",
            "encounter_id": None,
            "handoff_ticket_id": None,
            "doctor_turns": 0,
            "required_data": {
                "chief_complaint": "",
                "symptoms": [],
                "vitals": {},
            },
            "doctor_data": {
                "duration": "",
                "pain_score": None,
                "red_flags": {"fever": None, "breathing_difficulty": None, "worsening_pain": None},
                "informative_turns": 0,
            },
            "transcript": [],
            "call_status": "WAITING_FOR_TRIAGE",
            "queue_position": 0,
            "estimated_wait_minutes": 0,
            "movement_suggestion": {
                "target_zone": "triage_waiting_area",
                "instruction": "Please wait near triage waiting area.",
            },
        }
    return _USER_MODE_SESSION


def _missing_fields(session: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    req = session["required_data"]
    if not req["chief_complaint"].strip():
        missing.append("chief_complaint")
    if not req["symptoms"]:
        missing.append("symptoms")
    vitals = req["vitals"]
    if "spo2" not in vitals:
        missing.append("spo2")
    if "sbp" not in vitals:
        missing.append("sbp")
    return missing


def _question_for_missing(field_name: str) -> str:
    prompts = {
        "chief_complaint": "Please describe your chief complaint in one sentence.",
        "symptoms": "Please provide key symptoms (comma-separated is okay).",
        "spo2": "Please provide your SpO2 (blood oxygen), for example `spo2 95`.",
        "sbp": "Please provide your systolic blood pressure (SBP), for example `sbp 120`.",
    }
    return prompts[field_name]


def _append_transcript(session: Dict[str, Any], agent: str, text: str) -> None:
    session["transcript"].append(
        {
            "timestamp": _utc_now_iso(),
            "role": _role_label(agent),
            "text": text,
        }
    )


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


def user_mode_chat_turn(message: str) -> Dict[str, Any]:
    if not isinstance(message, str) or not message.strip():
        raise ApiError("`message` is required and must be non-empty")

    session = _ensure_user_session()
    msg = message.strip()
    _append_transcript(session, "PATIENT", msg)
    messages: List[Dict[str, str]] = []

    if session["phase"] == "INTAKE":
        req = session["required_data"]
        clean_msg = _normalize_text(msg)
        if _is_smalltalk(clean_msg) and not req["chief_complaint"]:
            ask = "Hi, I’m the triage nurse. What brought you in today, and how severe is it from 0 to 10?"
            session["current_agent"] = "TRIAGE_NURSE"
            session["call_status"] = "TRIAGE_INTAKE"
            _append_transcript(session, "TRIAGE_NURSE", ask)
            messages.append({"role": "triage_nurse", "text": ask})
            return {
                "session": _build_session_payload(session),
                "messages": messages,
                "transcript_tail": session["transcript"][-20:],
            }

        if not req["chief_complaint"] and not _is_smalltalk(clean_msg):
            req["chief_complaint"] = clean_msg
        parsed_symptoms = _extract_symptoms(clean_msg)
        if parsed_symptoms:
            req["symptoms"] = req["symptoms"] or parsed_symptoms
        elif req["chief_complaint"] and not req["symptoms"]:
            req["symptoms"] = _extract_symptoms(req["chief_complaint"])
        req["vitals"].update(_extract_vitals(msg))
        pain = _extract_pain_score(msg)
        if pain is not None:
            req["vitals"]["pain_score"] = float(pain)

        missing = _missing_fields(session)
        if _cannot_measure_vitals(clean_msg):
            measured = _nurse_measured_vitals(req.get("chief_complaint", ""), req.get("symptoms", []))
            for k, v in measured.items():
                req["vitals"].setdefault(k, v)
            missing = _missing_fields(session)
            if not missing:
                note = (
                    f"No problem, I measured your vitals in triage: SpO2 {int(req['vitals']['spo2'])}, "
                    f"SBP {int(req['vitals']['sbp'])}. We can continue now."
                )
                _append_transcript(session, "TRIAGE_NURSE", note)
                messages.append({"role": "triage_nurse", "text": note})

        if missing:
            ask = _agent_reply(
                "TRIAGE_NURSE",
                _next_intake_question(missing),
                session,
                extra={"missing_fields": missing, "patient_message": msg},
            )
            session["current_agent"] = "TRIAGE_NURSE"
            session["call_status"] = "TRIAGE_INTAKE"
            session["movement_suggestion"] = {
                "target_zone": "triage_waiting_area",
                "instruction": "Stay in triage waiting area and provide the requested info.",
            }
            _append_transcript(session, "TRIAGE_NURSE", ask)
            messages.append({"role": "triage_nurse", "text": ask})
        else:
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
            if _is_green_channel_encounter(encounter):
                session["phase"] = "DOCTOR_CALLED"
                session["current_agent"] = "DOCTOR"
                session["queue_position"] = 0
                session["estimated_wait_minutes"] = 0
                session["call_status"] = "CALLED"
                session["movement_suggestion"] = {
                    "target_zone": "doctor_assessment_zone",
                    "instruction": "Urgent triage channel activated. Please move to doctor assessment zone now.",
                }
                triage_line = _agent_reply(
                    "TRIAGE_NURSE",
                    (
                        f"Triage completed: acuity {encounter['triage']['acuity_ad']} "
                        f"(CTAS {encounter['triage']['ctas_compat']}). Green channel activated, "
                        "you will be seen by a doctor immediately."
                    ),
                    session,
                    extra={"triage": encounter.get("triage", {})},
                )
                _append_transcript(session, "TRIAGE_NURSE", triage_line)
                messages.append({"role": "triage_nurse", "text": triage_line})
                doctor_line = _agent_reply(
                    "DOCTOR",
                    "I’m the doctor. We are seeing you now via urgent channel. Please tell me your current symptoms and when they started.",
                    session,
                    extra={"patient_message": msg, "triage": encounter.get("triage", {})},
                )
                _append_transcript(session, "DOCTOR", doctor_line)
                messages.append({"role": "doctor", "text": doctor_line})
            else:
                session["phase"] = "WAITING_CALL"
                session["current_agent"] = "TRIAGE_NURSE"
                queue = _queue_metrics(session)
                session["queue_position"] = queue["before_me"]
                session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
                session["call_status"] = "WAITING_CALL"
                session["movement_suggestion"] = {
                    "target_zone": "triage_waiting_area",
                    "instruction": "Wait in queue and watch your call number.",
                }
                line = _agent_reply(
                    "TRIAGE_NURSE",
                    (
                    f"Triage completed: acuity {encounter['triage']['acuity_ad']} "
                    f"(CTAS {encounter['triage']['ctas_compat']}). "
                    f"There are about {session['queue_position']} patients before you."
                    ),
                    session,
                    extra={"triage": encounter.get("triage", {})},
                )
                _append_transcript(session, "TRIAGE_NURSE", line)
                messages.append({"role": "triage_nurse", "text": line})

    elif session["phase"] == "WAITING_CALL":
        queue = _queue_metrics(session)
        session["queue_position"] = queue["before_me"]
        session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
        if session["queue_position"] <= 0:
            session["phase"] = "DOCTOR_CALLED"
            session["current_agent"] = "DOCTOR"
            session["call_status"] = "CALLED"
            session["movement_suggestion"] = {
                "target_zone": "doctor_assessment_zone",
                "instruction": "Your number is called. Please move to doctor assessment zone.",
            }
            line = _agent_reply(
                "DOCTOR",
                "Your number is called. I am the doctor. Please describe your current symptoms, when they started, and whether you have fever or breathing difficulty.",
                session,
                extra={"patient_message": msg},
            )
            _append_transcript(session, "DOCTOR", line)
            messages.append({"role": "doctor", "text": line})
        else:
            line = _agent_reply(
                "TRIAGE_NURSE",
                (
                f"Please wait. {session['queue_position']} patients are before you, "
                f"estimated {session['estimated_wait_minutes']} minutes."
                ),
                session,
            )
            _append_transcript(session, "TRIAGE_NURSE", line)
            messages.append({"role": "triage_nurse", "text": line})

    elif session["phase"] == "DOCTOR_CALLED":
        session["call_status"] = "IN_CONSULTATION"
        _update_doctor_data(session, msg)
        missing_topics = _doctor_missing_topics(session)
        if not _doctor_ready_for_disposition(session):
            next_ask = "Thanks. Could you tell me more about symptom duration and whether anything is getting worse?"
            if "duration" in missing_topics:
                next_ask = "When did these symptoms start, and have they been getting worse?"
            elif "fever" in missing_topics:
                next_ask = "Do you currently have fever or chills?"
            elif "breathing_difficulty" in missing_topics:
                next_ask = "Do you have breathing difficulty right now?"
            elif "worsening_pain" in missing_topics:
                next_ask = "Is the pain worsening compared with earlier?"
            line = _agent_reply(
                "DOCTOR",
                next_ask,
                session,
                extra={"patient_message": msg, "doctor_missing_topics": missing_topics, "doctor_data": _doctor_data(session)},
            )
            _append_transcript(session, "DOCTOR", line)
            messages.append({"role": "doctor", "text": line})
        else:
            encounter = _ENCOUNTERS.get(session["encounter_id"], {})
            triage = encounter.get("triage", {})
            acuity = triage.get("acuity_ad", "C")
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
                session["current_agent"] = "BEDSIDE_NURSE"
                session["movement_suggestion"] = {
                    "target_zone": "bedside_transfer_zone",
                    "instruction": f"Proceed to bedside transfer area for {target} arrangement.",
                }
                line = _agent_reply(
                    "DOCTOR",
                    f"Assessment complete. Based on your current condition, we will arrange transfer to {target}. Bedside nurse will assist you now.",
                    session,
                    extra={"target_system": target, "patient_message": msg, "doctor_data": _doctor_data(session)},
                )
                _append_transcript(session, "DOCTOR", line)
                messages.append({"role": "doctor", "text": line})
            else:
                session["phase"] = "DONE"
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
                )
                _append_transcript(session, "DOCTOR", line)
                messages.append({"role": "doctor", "text": line})

    elif session["phase"] == "BED_NURSE_FLOW":
        if session.get("handoff_ticket_id"):
            complete = complete_handoff(
                {
                    "handoff_ticket_id": session["handoff_ticket_id"],
                    "receiver_system": "ICU"
                    if _ENCOUNTERS[session["encounter_id"]]["triage"]["acuity_ad"] in {"A", "B"}
                    else "WARD",
                    "accepted": True,
                    "receiver_bed": "BED-01",
                }
            )
            session["phase"] = "DONE"
            session["call_status"] = "COMPLETED"
            session["movement_suggestion"] = {
                "target_zone": "assigned_bed",
                "instruction": "Bed is arranged. Follow bedside nurse to assigned bed.",
            }
            line = _agent_reply(
                "BEDSIDE_NURSE",
                (
                f"Bed arrangement done. Destination: {complete['final_disposition_state']}, "
                f"transfer latency {complete['transfer_latency_seconds']} seconds."
                ),
                session,
                extra={"handoff_result": complete},
            )
            _append_transcript(session, "BEDSIDE_NURSE", line)
            messages.append({"role": "bed_nurse", "text": line})

    else:
        line = _agent_reply(
            "SYSTEM",
            "Current encounter is completed. Start a new session if needed.",
            session,
        )
        _append_transcript(session, "SYSTEM", line)
        messages.append({"role": "system", "text": line})

    return {
        "session": _build_session_payload(session),
        "messages": messages,
        "transcript_tail": session["transcript"][-20:],
    }


def user_mode_session_status() -> Dict[str, Any]:
    session = _ensure_user_session()
    if session["phase"] == "WAITING_CALL":
        queue = _queue_metrics(session)
        session["queue_position"] = queue["before_me"]
        session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
    return {
        "session": _build_session_payload(session),
        "transcript_tail": session["transcript"][-20:],
    }


def reset_user_mode_session() -> Dict[str, Any]:
    global _USER_MODE_SESSION
    _USER_MODE_SESSION = None
    session = _ensure_user_session()
    return {
        "session": _build_session_payload(session),
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
