from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from week5_system.rule_core.encounter import start_user_encounter
from week5_system.rule_core.triage_policy import TriageInput
from week5_system.app.schema import PayloadError, error_response, validate_encounter_start_payload


_TRACE_BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _iso_by_offset(offset_seconds: int) -> str:
    return (_TRACE_BASE_TS + timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")


def _build_event_trace(triage: Dict[str, object], state_trace: List[str]) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    offset = 0
    events.append(
        {
            "ts": _iso_by_offset(offset),
            "event": "triage_completed",
            "details": {"acuity_ad": triage.get("acuity_ad"), "zone": triage.get("zone")},
        }
    )
    offset += 1
    for hook in triage.get("hooks", []) or []:
        events.append(
            {"ts": _iso_by_offset(offset), "event": "hook_applied", "details": {"hook": hook}}
        )
        offset += 1
    for state in state_trace[1:]:
        events.append({"ts": _iso_by_offset(offset), "event": "state_transition", "state": state})
        offset += 1
    events.append(
        {"ts": _iso_by_offset(offset), "event": "encounter_completed", "state": state_trace[-1]}
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
