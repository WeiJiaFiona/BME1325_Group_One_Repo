from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from week5_system.rule_core.encounter import start_user_encounter
from week5_system.rule_core.triage_policy import TriageInput
from week5_system.app.schema import PayloadError, error_response, validate_encounter_start_payload


def _iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _build_event_trace(triage: Dict[str, object], state_trace: List[str]) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    events.append(
        {
            "ts": _iso_now(),
            "event": "triage_completed",
            "details": {"acuity_ad": triage.get("acuity_ad"), "zone": triage.get("zone")},
        }
    )
    for hook in triage.get("hooks", []) or []:
        events.append(
            {"ts": _iso_now(), "event": "hook_applied", "details": {"hook": hook}}
        )
    for state in state_trace[1:]:
        events.append({"ts": _iso_now(), "event": "state_transition", "state": state})
    events.append(
        {"ts": _iso_now(), "event": "encounter_completed", "state": state_trace[-1]}
    )
    return events


def start(payload: Dict[str, object]) -> Dict[str, object]:
    try:
        cleaned = validate_encounter_start_payload(payload)
        case = TriageInput(
            chief_complaint=cleaned["chief_complaint"],
            symptoms=cleaned["symptoms"],
            vitals=cleaned["vitals"],
            arrival_mode=cleaned["arrival_mode"],
        )
        patient_id = cleaned["patient_id"]
        result = start_user_encounter(patient_id, case)
        event_trace = _build_event_trace(result.triage, result.state_trace)
        return {
            "patient_id": result.patient_id,
            "triage": result.triage,
            "final_state": result.final_state,
            "state_trace": result.state_trace,
            "event_trace": event_trace,
        }
    except PayloadError as exc:
        field_errors = []
        if exc.field:
            field_errors = [{"field": exc.field, "error_code": exc.error_code, "message": exc.message}]
        return error_response(exc.error_code, exc.message, field_errors=field_errors)
