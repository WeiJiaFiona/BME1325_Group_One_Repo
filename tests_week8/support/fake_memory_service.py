"""Test-only fake memory services.

These are allowed in Week8 prework because they do NOT create a production substrate.
They exist only to let tests_week8 run before Developer A lands app_core/memory/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def env_flag(name: str, default: str = "1") -> bool:
    raw = (default if name not in __import__("os").environ else __import__("os").environ.get(name, default))
    v = str(raw).strip().lower()
    return v not in {"0", "false", "no", "off"}


@dataclass
class FakeMemoryItem:
    run_id: str
    mode: str
    encounter_id: str
    patient_id: str
    step: int
    agent_role: str
    event_type: str
    content: str
    structured_facts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeReplay:
    run_id: str
    mode: str
    encounter_id: str
    items: List[FakeMemoryItem]


class NullMemoryService:
    """Fail-open no-op."""

    def append_event(self, *_args, **_kwargs) -> Optional[str]:
        return None

    def upsert_current_summary(self, *_args, **_kwargs) -> None:
        return None

    def get_current_summary(self, *_args, **_kwargs) -> Optional[Dict[str, Any]]:
        return None

    def write_handoff_snapshot(self, *_args, **_kwargs) -> Optional[str]:
        return None

    def retrieve(self, *_args, **_kwargs) -> List[Dict[str, Any]]:
        return []

    def export_replay(self, *_args, **_kwargs) -> Dict[str, Any]:
        return {"ok": True, "events": [], "summaries": [], "snapshots": [], "audit": []}

    def append_audit(self, *_args, **_kwargs) -> None:
        return None


class InMemoryFakeService:
    """Tiny in-memory storage for tests_week8."""

    def __init__(self):
        self._seq: Dict[Tuple[str, str], int] = {}
        self._events: List[FakeMemoryItem] = []
        self._summaries: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def next_step(self, run_id: str, mode: str) -> int:
        key = (run_id, mode)
        self._seq[key] = int(self._seq.get(key, 0)) + 1
        return self._seq[key]

    def append_event(
        self,
        *,
        run_id: str,
        mode: str,
        encounter_id: str,
        patient_id: str,
        agent_role: str,
        event_type: str,
        content: str,
        structured_facts: Optional[Dict[str, Any]] = None,
    ) -> str:
        step = self.next_step(run_id, mode)
        item = FakeMemoryItem(
            run_id=run_id,
            mode=mode,
            encounter_id=encounter_id,
            patient_id=patient_id,
            step=step,
            agent_role=agent_role,
            event_type=event_type,
            content=content,
            structured_facts=dict(structured_facts or {}),
        )
        self._events.append(item)
        return f"mem-{step}"

    def upsert_current_summary(self, *, run_id: str, mode: str, encounter_id: str, summary: Dict[str, Any]) -> None:
        self._summaries[(run_id, mode, encounter_id)] = dict(summary)

    def get_current_summary(self, *, run_id: str, mode: str, encounter_id: str) -> Optional[Dict[str, Any]]:
        return self._summaries.get((run_id, mode, encounter_id))

    def retrieve(
        self,
        *,
        run_id: str,
        mode: str,
        encounter_id: str,
        top_k: int = 5,
        event_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        out = [e for e in self._events if e.run_id == run_id and e.mode == mode and e.encounter_id == encounter_id]
        if event_types:
            allowed = set(event_types)
            out = [e for e in out if e.event_type in allowed]
        out.sort(key=lambda x: x.step, reverse=True)
        return [e.__dict__ for e in out[: int(top_k)]]

    def export_replay(self, *, run_id: str, mode: str, encounter_id: str) -> Dict[str, Any]:
        items = [e for e in self._events if e.run_id == run_id and e.mode == mode and e.encounter_id == encounter_id]
        items.sort(key=lambda x: x.step)
        return {
            "ok": True,
            "run_id": run_id,
            "mode": mode,
            "encounter_id": encounter_id,
            "events": [e.__dict__ for e in items],
            "summaries": [self._summaries.get((run_id, mode, encounter_id), {})],
            "snapshots": [],
            "audit": [],
        }
