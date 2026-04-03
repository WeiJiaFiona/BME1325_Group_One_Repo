from __future__ import annotations

from typing import Dict

from week5_system.rule_core.encounter import start_user_encounter
from week5_system.rule_core.triage_policy import TriageInput


def start(payload: Dict[str, object]) -> Dict[str, object]:
    case = TriageInput(
        chief_complaint=str(payload.get("chief_complaint", "")),
        symptoms=list(payload.get("symptoms", [])),
        vitals=dict(payload.get("vitals", {})),
        arrival_mode=str(payload.get("arrival_mode", "walk-in")),
    )
    patient_id = str(payload.get("patient_id", "patient-unknown"))
    result = start_user_encounter(patient_id, case)
    return {
        "patient_id": result.patient_id,
        "triage": result.triage,
        "final_state": result.final_state,
        "state_trace": result.state_trace,
    }
