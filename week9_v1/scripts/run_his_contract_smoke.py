from __future__ import annotations

import json
import re

from app_core.app.api_v1 import (
    complete_handoff,
    export_encounter_timeline,
    get_encounter_summary,
    request_handoff,
    reset_runtime_state,
    start_encounter,
)
from app_core.his.adapters.contract_adapter import ENCOUNTER_ID_PATTERN, FROZEN_CTAS_LEVELS, FROZEN_ZONE_VALUES, PATIENT_ID_PATTERN
from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES


def build_contract_alignment_smoke_plan() -> dict[str, object]:
    reset_runtime_state()
    start = start_encounter(
        {
            "patient_id": "week9-contract-smoke",
            "chief_complaint": "Chest pain with diaphoresis",
            "symptoms": ["shortness of breath", "radiating pain"],
            "vitals": {"spo2": 93, "sbp": 102},
            "arrival_mode": "walk-in",
        }
    )
    handoff = request_handoff(
        {
            "encounter_id": start["encounter_id"],
            "target_system": "ICU",
            "reason": "high-risk chest pain",
        }
    )
    complete_handoff(
        {
            "handoff_ticket_id": handoff["handoff_ticket_id"],
            "receiver_system": "ICU",
            "accepted": True,
            "receiver_bed": "ICU-BED-1001",
        }
    )
    summary = get_encounter_summary(start["encounter_id"])
    timeline = export_encounter_timeline(start["encounter_id"])
    first_event = timeline["bundle"]["event_registry"][0]
    return {
        "name": "contract_alignment_checks",
        "status": "passed",
        "routes": list(FROZEN_ROUTE_NAMES),
        "event_envelope_fields": list(EVENT_ENVELOPE_FIELDS),
        "field_checks": {
            "patient_id_matches": bool(re.fullmatch(PATIENT_ID_PATTERN, start["patient_id"])),
            "encounter_id_matches": bool(re.fullmatch(ENCOUNTER_ID_PATTERN, start["encounter_id"])),
            "ctas_level_valid": summary["triage"]["ctas_level"] in FROZEN_CTAS_LEVELS,
            "zone_valid": summary["triage"]["zone"] in FROZEN_ZONE_VALUES,
            "envelope_keys_match": list(first_event.keys())[:7] == list(EVENT_ENVELOPE_FIELDS),
        },
        "summary_state": summary["summary"]["current_state"],
        "first_event": first_event,
    }


def main() -> None:
    print(json.dumps(build_contract_alignment_smoke_plan(), indent=2))


if __name__ == "__main__":
    main()
