from __future__ import annotations

from app_core.app.api_v1 import complete_handoff, get_encounter_summary, request_handoff, reset_runtime_state, start_encounter


def test_handoff_and_summary_views_stay_connected() -> None:
    reset_runtime_state()
    start = start_encounter(
        {
            "patient_id": "week9-connectivity",
            "chief_complaint": "Severe chest pain",
            "symptoms": ["shortness of breath", "radiating pain"],
            "vitals": {"spo2": 93, "sbp": 100},
            "arrival_mode": "walk-in",
        }
    )
    requested = request_handoff(
        {
            "encounter_id": start["encounter_id"],
            "target_system": "ICU",
            "reason": "high acuity transfer",
        }
    )
    complete_handoff(
        {
            "handoff_ticket_id": requested["handoff_ticket_id"],
            "receiver_system": "ICU",
            "accepted": True,
            "receiver_bed": "ICU-BED-3003",
        }
    )
    summary = get_encounter_summary(start["encounter_id"])
    assert summary["summary"]["current_state"] == "icu"
    assert summary["handoff_count"] >= 2
    assert summary["triage"]["ctas_level"] in {"L1", "L2", "L3", "L4", "L5"}
