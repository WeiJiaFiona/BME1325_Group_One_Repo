from __future__ import annotations

import json

from app_core.app.api_v1 import (
    complete_handoff,
    export_encounter_timeline,
    request_handoff,
    reset_runtime_state,
    start_encounter,
)


def build_timeline_export_smoke_plan() -> dict[str, object]:
    reset_runtime_state()
    start = start_encounter(
        {
            "patient_id": "week9-timeline-smoke",
            "chief_complaint": "Chest pain with shortness of breath",
            "symptoms": ["radiating pain", "dizziness"],
            "vitals": {"spo2": 94, "sbp": 104},
            "arrival_mode": "walk-in",
        }
    )
    handoff = request_handoff(
        {
            "encounter_id": start["encounter_id"],
            "target_system": "ICU",
            "reason": "timeline smoke transfer",
        }
    )
    complete_handoff(
        {
            "handoff_ticket_id": handoff["handoff_ticket_id"],
            "receiver_system": "ICU",
            "accepted": True,
            "receiver_bed": "ICU-BED-2002",
        }
    )
    timeline = export_encounter_timeline(start["encounter_id"])
    bundle = timeline["bundle"]
    return {
        "name": "timeline_export",
        "status": "passed",
        "encounter_id": start["encounter_id"],
        "sections": sorted(bundle.keys()),
        "counts": {
            "event_registry": len(bundle["event_registry"]),
            "handoff_snapshots": len(bundle["handoff_snapshots"]),
            "memory_events": len(bundle["memory_replay"]["events"]),
            "memory_summaries": len(bundle["memory_replay"]["summaries"]),
            "memory_snapshots": len(bundle["memory_replay"]["snapshots"]),
            "audit_logs": len(bundle["audit_logs"]),
        },
        "timeline_document_type": timeline["document"]["document_type"],
    }


def main() -> None:
    print(json.dumps(build_timeline_export_smoke_plan(), indent=2))


if __name__ == "__main__":
    main()
