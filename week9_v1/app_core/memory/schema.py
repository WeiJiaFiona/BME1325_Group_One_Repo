from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .taxonomy import CHECKPOINTS, EVENT_TYPES, MODES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_mode(value: Any) -> str:
    mode = _require_str(value, "mode")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {sorted(MODES)}")
    return mode


def _require_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an int")
    return value


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an int or None")
    return value


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    return dict(value)


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


def _ensure_tags(value: Any, field_name: str) -> list[str]:
    tags = _require_list(value, field_name)
    cleaned: list[str] = []
    for item in tags:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} items must be strings")
        cleaned.append(item)
    return cleaned


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    run_id: str
    mode: str
    encounter_id: str
    patient_id: str
    step: int
    sim_time: float | int | None
    wall_time: str | None
    agent_role: str
    event_type: str
    source: str
    priority: str | int
    content: str
    structured_facts: dict[str, Any] = field(default_factory=dict)
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)
    salience: float | int | None = None
    retrieval_scope: list[str] | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "memory_id", _require_str(self.memory_id, "memory_id"))
        object.__setattr__(self, "run_id", _require_str(self.run_id, "run_id"))
        object.__setattr__(self, "mode", _require_mode(self.mode))
        object.__setattr__(self, "encounter_id", _require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", _require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "step", _require_int(self.step, "step"))
        object.__setattr__(self, "agent_role", _require_str(self.agent_role, "agent_role"))
        event_type = _require_str(self.event_type, "event_type")
        if event_type not in EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(EVENT_TYPES)}")
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "source", _require_str(self.source, "source"))
        object.__setattr__(self, "content", _require_str(self.content, "content"))
        object.__setattr__(self, "structured_facts", _require_dict(self.structured_facts, "structured_facts"))
        if self.state_before is not None:
            object.__setattr__(self, "state_before", _require_dict(self.state_before, "state_before"))
        if self.state_after is not None:
            object.__setattr__(self, "state_after", _require_dict(self.state_after, "state_after"))
        object.__setattr__(self, "tags", _ensure_tags(self.tags, "tags"))
        if self.retrieval_scope is not None:
            object.__setattr__(self, "retrieval_scope", _ensure_tags(self.retrieval_scope, "retrieval_scope"))
        object.__setattr__(self, "created_at", _require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryItem":
        return cls(**dict(payload))


@dataclass(frozen=True)
class CurrentEncounterSummary:
    run_id: str
    mode: str
    encounter_id: str
    patient_id: str
    current_state: str
    current_zone: str | None
    acuity: str | None
    latest_vitals: dict[str, Any] = field(default_factory=dict)
    active_risks: list[dict[str, Any]] = field(default_factory=list)
    pending_tasks: list[dict[str, Any]] = field(default_factory=list)
    completed_actions: list[dict[str, Any]] = field(default_factory=list)
    latest_doctor_findings: dict[str, Any] = field(default_factory=dict)
    latest_test_status: dict[str, Any] = field(default_factory=dict)
    source_memory_ids: list[str] = field(default_factory=list)
    updated_at_step: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_str(self.run_id, "run_id"))
        object.__setattr__(self, "mode", _require_mode(self.mode))
        object.__setattr__(self, "encounter_id", _require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", _require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "current_state", _require_str(self.current_state, "current_state"))
        object.__setattr__(self, "latest_vitals", _require_dict(self.latest_vitals, "latest_vitals"))
        object.__setattr__(self, "latest_doctor_findings", _require_dict(self.latest_doctor_findings, "latest_doctor_findings"))
        object.__setattr__(self, "latest_test_status", _require_dict(self.latest_test_status, "latest_test_status"))
        object.__setattr__(self, "source_memory_ids", _ensure_tags(self.source_memory_ids, "source_memory_ids"))
        object.__setattr__(self, "updated_at_step", _require_int(self.updated_at_step, "updated_at_step"))
        for field_name in ("active_risks", "pending_tasks", "completed_actions"):
            value = _require_list(getattr(self, field_name), field_name)
            cleaned: list[dict[str, Any]] = []
            for item in value:
                cleaned.append(_require_dict(item, field_name))
            object.__setattr__(self, field_name, cleaned)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CurrentEncounterSummary":
        return cls(**dict(payload))


@dataclass(frozen=True)
class HandoffMemorySnapshot:
    snapshot_id: str
    run_id: str
    mode: str
    encounter_id: str
    patient_id: str
    from_role: str
    to_role: str
    handoff_stage: str
    patient_brief: str
    current_state: dict[str, Any]
    completed_actions: list[dict[str, Any]] = field(default_factory=list)
    pending_tasks: list[dict[str, Any]] = field(default_factory=list)
    active_risks: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    source_memory_ids: list[str] = field(default_factory=list)
    created_at_step: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _require_str(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "run_id", _require_str(self.run_id, "run_id"))
        object.__setattr__(self, "mode", _require_mode(self.mode))
        object.__setattr__(self, "encounter_id", _require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", _require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "from_role", _require_str(self.from_role, "from_role"))
        object.__setattr__(self, "to_role", _require_str(self.to_role, "to_role"))
        stage = _require_str(self.handoff_stage, "handoff_stage")
        if stage not in {"requested", "completed"}:
            raise ValueError("handoff_stage must be one of ['completed', 'requested']")
        object.__setattr__(self, "handoff_stage", stage)
        object.__setattr__(self, "patient_brief", _require_str(self.patient_brief, "patient_brief"))
        object.__setattr__(self, "current_state", _require_dict(self.current_state, "current_state"))
        object.__setattr__(self, "source_memory_ids", _ensure_tags(self.source_memory_ids, "source_memory_ids"))
        object.__setattr__(self, "created_at_step", _require_int(self.created_at_step, "created_at_step"))
        for field_name in ("completed_actions", "pending_tasks", "active_risks", "next_actions"):
            value = _require_list(getattr(self, field_name), field_name)
            cleaned: list[dict[str, Any]] = []
            for item in value:
                cleaned.append(_require_dict(item, field_name))
            object.__setattr__(self, field_name, cleaned)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HandoffMemorySnapshot":
        return cls(**dict(payload))


@dataclass(frozen=True)
class MemoryQuery:
    run_id: str
    mode: str
    encounter_id: str
    checkpoint: str
    agent_role: str | None = None
    event_types: list[str] | None = None
    tags: list[str] | None = None
    top_k: int = 5
    max_age_steps: int | None = 20
    include_snapshots: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_str(self.run_id, "run_id"))
        object.__setattr__(self, "mode", _require_mode(self.mode))
        object.__setattr__(self, "encounter_id", _require_str(self.encounter_id, "encounter_id"))
        checkpoint = _require_str(self.checkpoint, "checkpoint")
        if checkpoint not in CHECKPOINTS:
            raise ValueError(f"checkpoint must be one of {sorted(CHECKPOINTS)}")
        object.__setattr__(self, "checkpoint", checkpoint)
        if self.agent_role is not None:
            object.__setattr__(self, "agent_role", _require_str(self.agent_role, "agent_role"))
        if self.event_types is not None:
            cleaned_event_types = _ensure_tags(self.event_types, "event_types")
            for item in cleaned_event_types:
                if item not in EVENT_TYPES:
                    raise ValueError(f"Unknown event type in event_types: {item}")
            object.__setattr__(self, "event_types", cleaned_event_types)
        if self.tags is not None:
            object.__setattr__(self, "tags", _ensure_tags(self.tags, "tags"))
        top_k = _require_int(self.top_k, "top_k")
        if top_k < 1 or top_k > 5:
            raise ValueError("top_k must be between 1 and 5")
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "max_age_steps", _optional_int(self.max_age_steps, "max_age_steps"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryQuery":
        return cls(**dict(payload))


@dataclass(frozen=True)
class AuditRecord:
    op_id: str
    run_id: str
    mode: str
    encounter_id: str
    op_type: str
    checkpoint: str
    source_ids: list[str] = field(default_factory=list)
    top_k: int | None = None
    latency_ms: float | int | None = None
    timestamp: str = field(default_factory=utc_now_iso)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "op_id", _require_str(self.op_id, "op_id"))
        object.__setattr__(self, "run_id", _require_str(self.run_id, "run_id"))
        object.__setattr__(self, "mode", _require_mode(self.mode))
        object.__setattr__(self, "encounter_id", _require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "op_type", _require_str(self.op_type, "op_type"))
        checkpoint = _require_str(self.checkpoint, "checkpoint")
        if checkpoint not in CHECKPOINTS:
            raise ValueError(f"checkpoint must be one of {sorted(CHECKPOINTS)}")
        object.__setattr__(self, "checkpoint", checkpoint)
        object.__setattr__(self, "source_ids", _ensure_tags(self.source_ids, "source_ids"))
        object.__setattr__(self, "details", _require_dict(self.details, "details"))
        object.__setattr__(self, "timestamp", _require_str(self.timestamp, "timestamp"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditRecord":
        return cls(**dict(payload))
