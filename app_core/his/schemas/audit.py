from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import EVENT_ENVELOPE_FIELDS, utc_now_iso

from ._base import ensure_tags, require_dict, require_str


@dataclass(frozen=True)
class EventRegistryEntry:
    event_id: str
    event_type: str
    occurred_at: str
    patient_id: str
    encounter_id: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_str(self.event_id, "event_id"))
        object.__setattr__(self, "event_type", require_str(self.event_type, "event_type"))
        object.__setattr__(self, "occurred_at", require_str(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "source", require_str(self.source, "source"))
        object.__setattr__(self, "payload", require_dict(self.payload, "payload"))
        object.__setattr__(self, "tags", ensure_tags(self.tags, "tags"))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for field_name in EVENT_ENVELOPE_FIELDS:
            data.setdefault(field_name, getattr(self, field_name))
        return data


@dataclass(frozen=True)
class AuditLogEntry:
    audit_id: str
    action: str
    actor: str
    patient_id: str | None = None
    encounter_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_id", require_str(self.audit_id, "audit_id"))
        object.__setattr__(self, "action", require_str(self.action, "action"))
        object.__setattr__(self, "actor", require_str(self.actor, "actor"))
        object.__setattr__(self, "details", require_dict(self.details, "details"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
