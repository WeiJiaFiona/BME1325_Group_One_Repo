from __future__ import annotations

from app_core.his.schemas import EventRegistryEntry
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def append_event_registry_entry(
    entry: EventRegistryEntry,
    storage: HisStorage | None = None,
) -> EventRegistryEntry:
    return resolve_storage(storage).append_event(entry)
