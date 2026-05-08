from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

from app_core.his.config import utc_now_iso


@dataclass(frozen=True)
class OutboxEvent:
    outbox_id: str = field(default_factory=lambda: f"outbox-{uuid.uuid4().hex[:12]}")
    event_type: str = "unknown"
    encounter_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_outbox_event(*, event_type: str, encounter_id: str, payload: dict[str, Any]) -> OutboxEvent:
    return OutboxEvent(event_type=event_type, encounter_id=encounter_id, payload=dict(payload))
