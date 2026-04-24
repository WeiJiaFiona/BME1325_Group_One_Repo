from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import AuditTrail
from .config import get_runtime_root, memory_v1_enabled
from .current_memory import CurrentEncounterMemory
from .episode_memory import EpisodeMemoryEventLog
from .handoff_memory import HandoffMemoryStore
from .replay_buffer import ExperienceReplayBuffer
from .retrieval import BoundedMemoryRetriever
from .schema import AuditRecord, CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem, MemoryQuery
from .storage import JsonFileMemoryStorage, MemoryStorage, NullMemoryStorage


class MemoryService:
    def __init__(self, storage: MemoryStorage, *, enabled: bool = True) -> None:
        self.storage = storage
        self.enabled = enabled
        self.events = EpisodeMemoryEventLog(storage)
        self.current = CurrentEncounterMemory(storage)
        self.handoffs = HandoffMemoryStore(storage)
        self.retriever = BoundedMemoryRetriever(storage)
        self.audit = AuditTrail(storage)
        self.replay = ExperienceReplayBuffer(storage) if isinstance(storage, JsonFileMemoryStorage) else None

    def append_event(self, item: MemoryItem | dict[str, Any]) -> MemoryItem | None:
        if not self.enabled:
            return None
        record = item if isinstance(item, MemoryItem) else MemoryItem.from_dict(item)
        return self.events.append(record)

    def update_current_summary(
        self,
        summary: CurrentEncounterSummary | dict[str, Any],
    ) -> CurrentEncounterSummary | None:
        if not self.enabled:
            return None
        record = summary if isinstance(summary, CurrentEncounterSummary) else CurrentEncounterSummary.from_dict(summary)
        return self.current.upsert(record)

    # Compatibility alias: earlier drafts used upsert_current_summary(...)
    upsert_current_summary = update_current_summary

    def get_current_summary(self, run_id: str, mode: str, encounter_id: str) -> CurrentEncounterSummary | None:
        if not self.enabled:
            return None
        return self.current.get(run_id, mode, encounter_id)

    def write_handoff_snapshot(
        self,
        snapshot: HandoffMemorySnapshot | dict[str, Any],
    ) -> HandoffMemorySnapshot | None:
        if not self.enabled:
            return None
        record = snapshot if isinstance(snapshot, HandoffMemorySnapshot) else HandoffMemorySnapshot.from_dict(snapshot)
        return self.handoffs.write(record)

    def retrieve(self, query: MemoryQuery | dict[str, Any]) -> list[MemoryItem]:
        if not self.enabled:
            return []
        request = query if isinstance(query, MemoryQuery) else MemoryQuery.from_dict(query)
        return self.retriever.retrieve(request)

    def export_replay(self, **kwargs: Any) -> dict[str, Any]:
        if not self.enabled or self.replay is None:
            return {"events": [], "summaries": [], "snapshots": [], "audits": []}
        return self.replay.export(**kwargs)

    def export_replay_to_path(self, destination: Path, **kwargs: Any) -> Path | None:
        if not self.enabled or self.replay is None:
            return None
        return self.replay.export_to_path(destination, **kwargs)

    def append_audit(self, record: AuditRecord | dict[str, Any]) -> AuditRecord | None:
        if not self.enabled:
            return None
        item = record if isinstance(record, AuditRecord) else AuditRecord.from_dict(record)
        return self.audit.append(item)


def create_memory_service(
    *,
    root: Path | None = None,
    enabled: bool | None = None,
    storage: MemoryStorage | None = None,
) -> MemoryService:
    resolved_enabled = memory_v1_enabled() if enabled is None else enabled
    if storage is not None:
        resolved_storage = storage
    elif resolved_enabled:
        resolved_storage = JsonFileMemoryStorage(root=root or get_runtime_root())
    else:
        resolved_storage = NullMemoryStorage()
    return MemoryService(resolved_storage, enabled=resolved_enabled)
