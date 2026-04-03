from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .state_machine import HOOK_ESCALATIONS, EncounterStateMachine
from .triage_policy import TriageInput, triage_cn_ad


@dataclass(frozen=True)
class EncounterResult:
    patient_id: str
    triage: Dict[str, object]
    final_state: str
    state_trace: List[str]


def start_user_encounter(patient_id: str, case: TriageInput) -> EncounterResult:
    triage = triage_cn_ad(case)
    machine = EncounterStateMachine()
    machine.transition("WAITING_FOR_TRIAGE")
    machine.transition("TRIAGE_COMPLETE")
    machine.transition("ROUTED")

    for hook in sorted(triage.hooks):
        if hook in HOOK_ESCALATIONS:
            machine.apply_hook(hook)

    if machine.current_state == "ROUTED":
        machine.transition("WAITING_FOR_PHYSICIAN")

    return EncounterResult(
        patient_id=patient_id,
        triage={
            "acuity_ad": triage.acuity_ad,
            "level_1_4": triage.level_1_4,
            "ctas_compat": triage.ctas_compat,
            "zone": triage.zone,
            "green_channel": triage.green_channel,
            "required_resources_count": triage.required_resources_count,
            "max_wait_minutes": triage.max_wait_minutes,
            "hooks": sorted(triage.hooks),
        },
        final_state=machine.current_state,
        state_trace=machine.trace,
    )
