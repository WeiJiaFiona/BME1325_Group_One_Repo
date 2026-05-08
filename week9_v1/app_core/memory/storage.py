from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from .config import get_runtime_root
from .schema import AuditRecord, CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem, MemoryQuery


class MemoryStorage(ABC):
    @abstractmethod
    def append_event(self, item: MemoryItem) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_current_summary(self, summary: CurrentEncounterSummary) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_current_summary(self, run_id: str, mode: str, encounter_id: str) -> CurrentEncounterSummary | None:
        raise NotImplementedError

    @abstractmethod
    def write_snapshot(self, snapshot: HandoffMemorySnapshot) -> None:
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, query: MemoryQuery) -> list[MemoryItem]:
        raise NotImplementedError

    @abstractmethod
    def append_audit(self, audit_record: AuditRecord) -> None:
        raise NotImplementedError


class NullMemoryStorage(MemoryStorage):
    def append_event(self, item: MemoryItem) -> None:
        return None

    def upsert_current_summary(self, summary: CurrentEncounterSummary) -> None:
        return None

    def get_current_summary(self, run_id: str, mode: str, encounter_id: str) -> CurrentEncounterSummary | None:
        return None

    def write_snapshot(self, snapshot: HandoffMemorySnapshot) -> None:
        return None

    def retrieve(self, query: MemoryQuery) -> list[MemoryItem]:
        return []

    def append_audit(self, audit_record: AuditRecord) -> None:
        return None


class JsonFileMemoryStorage(MemoryStorage):
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else get_runtime_root()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def audits_path(self) -> Path:
        return self.root / "audit.jsonl"

    def _current_summary_path(self, run_id: str, mode: str, encounter_id: str) -> Path:
        return self.root / "current" / mode / run_id / f"{encounter_id}.json"

    def _snapshot_path(self, snapshot: HandoffMemorySnapshot) -> Path:
        return (
            self.root
            / "snapshots"
            / snapshot.mode
            / snapshot.run_id
            / snapshot.encounter_id
            / f"{snapshot.snapshot_id}.json"
        )

    def append_event(self, item: MemoryItem) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    def upsert_current_summary(self, summary: CurrentEncounterSummary) -> None:
        path = self._current_summary_path(summary.run_id, summary.mode, summary.encounter_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def get_current_summary(self, run_id: str, mode: str, encounter_id: str) -> CurrentEncounterSummary | None:
        path = self._current_summary_path(run_id, mode, encounter_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CurrentEncounterSummary.from_dict(payload)

    def write_snapshot(self, snapshot: HandoffMemorySnapshot) -> None:
        path = self._snapshot_path(snapshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def retrieve(self, query: MemoryQuery) -> list[MemoryItem]:
        if not self.events_path.exists():
            return []

        matches: list[MemoryItem] = []
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = MemoryItem.from_dict(json.loads(line))
                if item.run_id != query.run_id or item.mode != query.mode or item.encounter_id != query.encounter_id:
                    continue
                if query.agent_role and item.agent_role != query.agent_role:
                    continue
                if query.event_types and item.event_type not in query.event_types:
                    continue
                if query.tags and not set(query.tags).issubset(set(item.tags)):
                    continue
                matches.append(item)

        if query.max_age_steps is not None and matches:
            latest_step = max(item.step for item in matches)
            min_step = latest_step - query.max_age_steps
            matches = [item for item in matches if item.step >= min_step]

        matches.sort(key=lambda item: (item.step, float(item.salience or 0)), reverse=True)
        return matches[: query.top_k]

    def append_audit(self, audit_record: AuditRecord) -> None:
        self.audits_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audits_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_record.to_dict(), ensure_ascii=False) + "\n")

    def list_snapshots(
        self,
        *,
        run_id: str | None = None,
        mode: str | None = None,
        encounter_id: str | None = None,
    ) -> list[HandoffMemorySnapshot]:
        root = self.root / "snapshots"
        if mode:
            root = root / mode
        if run_id:
            root = root / run_id
        if encounter_id:
            root = root / encounter_id
        if not root.exists():
            return []
        snapshots: list[HandoffMemorySnapshot] = []
        for path in sorted(root.rglob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            snapshot = HandoffMemorySnapshot.from_dict(payload)
            snapshots.append(snapshot)
        return snapshots

    def list_audits(
        self,
        *,
        run_id: str | None = None,
        mode: str | None = None,
        encounter_id: str | None = None,
    ) -> list[AuditRecord]:
        if not self.audits_path.exists():
            return []
        records: list[AuditRecord] = []
        with self.audits_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = AuditRecord.from_dict(json.loads(line))
                if run_id and record.run_id != run_id:
                    continue
                if mode and record.mode != mode:
                    continue
                if encounter_id and record.encounter_id != encounter_id:
                    continue
                records.append(record)
        return records
