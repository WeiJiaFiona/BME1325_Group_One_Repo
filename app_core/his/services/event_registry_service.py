from __future__ import annotations

from typing import Optional

from app_core.his.schemas import EventRegistryEntry
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def append_event_registry_entry(
    entry: EventRegistryEntry,
    storage: Optional[HisStorage] = None,
) -> EventRegistryEntry:
    return resolve_storage(storage).append_event(entry)


def list_event_registry_entries(
    encounter_id: str,
    storage: Optional[HisStorage] = None,
) -> list[EventRegistryEntry]:
    return resolve_storage(storage).list_events(encounter_id)
