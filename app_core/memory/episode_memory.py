from __future__ import annotations

from .schema import MemoryItem
from .storage import MemoryStorage


class EpisodeMemoryEventLog:
    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def append(self, item: MemoryItem) -> MemoryItem:
        self.storage.append_event(item)
        return item
