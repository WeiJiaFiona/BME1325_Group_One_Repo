from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "ARRIVAL": {"WAITING_FOR_TRIAGE"},
    "WAITING_FOR_TRIAGE": {"TRIAGE_COMPLETE", "LWBS"},
    "TRIAGE_COMPLETE": {"ROUTED"},
    "ROUTED": {"WAITING_FOR_PHYSICIAN", "UNDER_EVALUATION"},
    "WAITING_FOR_PHYSICIAN": {"UNDER_EVALUATION", "LWBS"},
    "UNDER_EVALUATION": {"WAITING_FOR_LAB", "WAITING_FOR_IMAGING", "UNDER_TREATMENT"},
    "WAITING_FOR_LAB": {"UNDER_TREATMENT"},
    "WAITING_FOR_IMAGING": {"UNDER_TREATMENT"},
    "UNDER_TREATMENT": {"OBSERVATION", "AWAITING_DISPOSITION"},
    "OBSERVATION": {"UNDER_TREATMENT", "AWAITING_DISPOSITION"},
    "AWAITING_DISPOSITION": {"ADMITTED", "ICU", "OR", "DISCHARGED", "TRANSFER", "LWBS"},
    "ADMITTED": {"LEAVE_ED"},
    "ICU": {"LEAVE_ED"},
    "OR": {"LEAVE_ED"},
    "DISCHARGED": {"LEAVE_ED"},
    "TRANSFER": {"LEAVE_ED"},
    "LWBS": {"LEAVE_ED"},
    "LEAVE_ED": set(),
}

HOOK_ESCALATIONS = {
    "green_channel": "UNDER_EVALUATION",
    "abnormal_vitals": "UNDER_EVALUATION",
    "deterioration": "ICU",
    "consult_required": "AWAITING_DISPOSITION",
    "icu_required": "ICU",
    "surgery_required": "OR",
}


@dataclass
class EncounterStateMachine:
    current_state: str = "ARRIVAL"
    trace: List[str] = field(default_factory=lambda: ["ARRIVAL"])

    def transition(self, next_state: str) -> None:
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, set())
        if next_state not in allowed:
            raise ValueError(
                f"Illegal transition: {self.current_state} -> {next_state}"
            )
        self.current_state = next_state
        self.trace.append(next_state)

    def apply_hook(self, hook: str) -> None:
        if hook not in HOOK_ESCALATIONS:
            raise ValueError(f"Unknown escalation hook: {hook}")
        target = HOOK_ESCALATIONS[hook]

        if target in ALLOWED_TRANSITIONS.get(self.current_state, set()):
            self.transition(target)
            return

        if target == "UNDER_EVALUATION":
            if self.current_state == "WAITING_FOR_TRIAGE":
                self.transition("TRIAGE_COMPLETE")
            if self.current_state == "TRIAGE_COMPLETE":
                self.transition("ROUTED")
            if self.current_state in {"ROUTED", "WAITING_FOR_PHYSICIAN"}:
                self.transition("UNDER_EVALUATION")
                return

        raise ValueError(f"Hook {hook} cannot be applied from {self.current_state}")
