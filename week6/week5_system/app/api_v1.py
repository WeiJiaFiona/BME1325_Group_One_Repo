from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
import re

from week5_system.app.mode_user import start as run_user_mode


ALLOWED_RECEIVER_SYSTEMS = {"OUTPATIENT", "ICU", "WARD"}


@dataclass
class ApiError(Exception):
    message: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


_ENCOUNTERS: Dict[str, Dict[str, Any]] = {}
_HANDOFF_TICKETS: Dict[str, Dict[str, Any]] = {}
_USER_MODE_SESSION: Optional[Dict[str, Any]] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _require_type(payload: Dict[str, Any], key: str, expected: type) -> Any:
    if key not in payload:
        raise ApiError(f"Missing required field: {key}")
    value = payload[key]
    if not isinstance(value, expected):
        raise ApiError(f"Invalid type for field `{key}`: expected {expected.__name__}")
    return value


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


def _extract_vitals(text: str) -> Dict[str, float]:
    t = text.lower()
    out: Dict[str, float] = {}
    spo2_match = re.search(r"(spo2|血氧)[^\d]{0,6}(\d{2,3})", t)
    sbp_match = re.search(r"(sbp|收缩压)[^\d]{0,6}(\d{2,3})", t)
    if spo2_match:
        out["spo2"] = float(spo2_match.group(2))
    if sbp_match:
        out["sbp"] = float(sbp_match.group(2))
    return out


def _extract_symptoms(text: str) -> List[str]:
    raw = text.strip()
    if not raw:
        return []
    if "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
    elif "，" in raw:
        parts = [p.strip() for p in raw.split("，") if p.strip()]
    else:
        parts = [raw]
    uniq: List[str] = []
    seen = set()
    for p in parts:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


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


def user_mode_chat_turn(message: str) -> Dict[str, Any]:
    if not isinstance(message, str) or not message.strip():
        raise ApiError("`message` is required and must be non-empty")

    session = _ensure_user_session()
    msg = message.strip()
    _append_transcript(session, "PATIENT", msg)
    messages: List[Dict[str, str]] = []

    if session["phase"] == "INTAKE":
        req = session["required_data"]
        if not req["chief_complaint"]:
            req["chief_complaint"] = msg
        req["symptoms"] = req["symptoms"] or _extract_symptoms(msg)
        req["vitals"].update(_extract_vitals(msg))

        missing = _missing_fields(session)
        if missing:
            ask = _question_for_missing(missing[0])
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
            line = (
                f"Triage completed: acuity {encounter['triage']['acuity_ad']} "
                f"(CTAS {encounter['triage']['ctas_compat']}). "
                f"There are about {session['queue_position']} patients before you."
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
            line = "Your number is called. I am the doctor. Please describe current discomfort and duration."
            _append_transcript(session, "DOCTOR", line)
            messages.append({"role": "doctor", "text": line})
        else:
            line = (
                f"Please wait. {session['queue_position']} patients are before you, "
                f"estimated {session['estimated_wait_minutes']} minutes."
            )
            _append_transcript(session, "TRIAGE_NURSE", line)
            messages.append({"role": "triage_nurse", "text": line})

    elif session["phase"] == "DOCTOR_CALLED":
        session["call_status"] = "IN_CONSULTATION"
        session["doctor_turns"] += 1
        if session["doctor_turns"] < 2:
            line = "Noted. Do you have fever, worsening pain, or breathing difficulty right now?"
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
                line = f"Assessment complete. We will arrange transfer to {target}. Bedside nurse will assist you now."
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
                line = "Assessment complete. Follow outpatient pathway for next management."
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
            line = (
                f"Bed arrangement done. Destination: {complete['final_disposition_state']}, "
                f"transfer latency {complete['transfer_latency_seconds']} seconds."
            )
            _append_transcript(session, "BEDSIDE_NURSE", line)
            messages.append({"role": "bed_nurse", "text": line})

    else:
        line = "Current encounter is completed. Start a new session if needed."
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
    patient_id = _require_type(payload, "patient_id", str).strip()
    chief_complaint = _require_type(payload, "chief_complaint", str).strip()
    symptoms = _require_type(payload, "symptoms", list)
    vitals = _require_type(payload, "vitals", dict)

    if not patient_id:
        raise ApiError("`patient_id` cannot be empty")
    if not chief_complaint:
        raise ApiError("`chief_complaint` cannot be empty")
    if not all(isinstance(item, str) for item in symptoms):
        raise ApiError("`symptoms` must be a list of strings")

    user_payload = {
        "patient_id": patient_id,
        "chief_complaint": chief_complaint,
        "symptoms": symptoms,
        "vitals": vitals,
        "arrival_mode": str(payload.get("arrival_mode", "walk-in")),
    }
    result = run_user_mode(user_payload)

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
