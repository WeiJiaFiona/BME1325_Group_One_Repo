from __future__ import annotations

from .schema import HandoffMemorySnapshot
from .storage import MemoryStorage


class HandoffMemoryStore:
    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def write(self, snapshot: HandoffMemorySnapshot) -> HandoffMemorySnapshot:
        self.storage.write_snapshot(snapshot)
        return snapshot
