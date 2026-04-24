from __future__ import annotations

from .schema import CurrentEncounterSummary
from .storage import MemoryStorage


class CurrentEncounterMemory:
    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def upsert(self, summary: CurrentEncounterSummary) -> CurrentEncounterSummary:
        self.storage.upsert_current_summary(summary)
        return summary

    def get(self, run_id: str, mode: str, encounter_id: str) -> CurrentEncounterSummary | None:
        return self.storage.get_current_summary(run_id, mode, encounter_id)
