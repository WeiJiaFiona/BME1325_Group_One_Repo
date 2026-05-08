from __future__ import annotations

from app_core.his.exchange.outbox import OutboxEvent, build_outbox_event
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def enqueue_outbox_event(
    *,
    event_type: str,
    encounter_id: str,
    payload: dict[str, object],
    storage: HisStorage | None = None,
) -> OutboxEvent:
    event = build_outbox_event(event_type=event_type, encounter_id=encounter_id, payload=payload)
    return resolve_storage(storage).append_outbox_event(event)


def list_outbox_events(
    encounter_id: str | None = None,
    storage: HisStorage | None = None,
) -> list[OutboxEvent]:
    return resolve_storage(storage).list_outbox_events(encounter_id)
