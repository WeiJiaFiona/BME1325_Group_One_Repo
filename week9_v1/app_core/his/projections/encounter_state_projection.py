from __future__ import annotations

from app_core.his.schemas import CurrentSummaryRecord, EventRegistryEntry


def project_encounter_state(
    *,
    encounter_id: str,
    latest_summary: CurrentSummaryRecord | None,
    latest_event: EventRegistryEntry | None,
) -> dict[str, object]:
    return {
        "encounter_id": encounter_id,
        "summary_state": latest_summary.current_state if latest_summary else None,
        "latest_event_type": latest_event.event_type if latest_event else None,
    }
