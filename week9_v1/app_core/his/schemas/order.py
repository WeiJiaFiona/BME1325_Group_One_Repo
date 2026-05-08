from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import utc_now_iso

from ._base import require_dict, require_str


@dataclass(frozen=True)
class OrderRecord:
    encounter_id: str
    patient_id: str
    order_id: str
    order_type: str
    status: str = "REQUESTED"
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "order_id", require_str(self.order_id, "order_id"))
        object.__setattr__(self, "order_type", require_str(self.order_type, "order_type"))
        object.__setattr__(self, "status", require_str(self.status, "status"))
        object.__setattr__(self, "payload", require_dict(self.payload, "payload"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
