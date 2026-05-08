from __future__ import annotations

from .schema import MemoryItem, MemoryQuery
from .storage import MemoryStorage


class BoundedMemoryRetriever:
    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def retrieve(self, query: MemoryQuery) -> list[MemoryItem]:
        return self.storage.retrieve(query)
