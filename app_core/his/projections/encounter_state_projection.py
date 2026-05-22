from __future__ import annotations

from typing import Optional

from app_core.his.schemas import CurrentSummaryRecord, EventRegistryEntry


def project_encounter_state(
    *,
    encounter_id: str,
    latest_summary: Optional[CurrentSummaryRecord],
    latest_event: Optional[EventRegistryEntry],
) -> dict[str, object]:
    return {
        "encounter_id": encounter_id,
        "summary_state": latest_summary.current_state if latest_summary else None,
        "latest_event_type": latest_event.event_type if latest_event else None,
    }
