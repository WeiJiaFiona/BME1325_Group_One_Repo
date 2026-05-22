from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import utc_now_iso

from ._base import require_dict, require_str


@dataclass(frozen=True)
class LabRequestRecord:
    encounter_id: str
    patient_id: str
    request_id: str
    order_id: str
    test_code: str
    status: str = "REQUESTED"
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "request_id", require_str(self.request_id, "request_id"))
        object.__setattr__(self, "order_id", require_str(self.order_id, "order_id"))
        object.__setattr__(self, "test_code", require_str(self.test_code, "test_code"))
        object.__setattr__(self, "status", require_str(self.status, "status"))
        object.__setattr__(self, "payload", require_dict(self.payload, "payload"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LabResultRecord:
    encounter_id: str
    patient_id: str
    result_id: str
    request_id: str
    status: str = "FINAL"
    payload: dict[str, Any] = field(default_factory=dict)
    resulted_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "result_id", require_str(self.result_id, "result_id"))
        object.__setattr__(self, "request_id", require_str(self.request_id, "request_id"))
        object.__setattr__(self, "status", require_str(self.status, "status"))
        object.__setattr__(self, "payload", require_dict(self.payload, "payload"))
        object.__setattr__(self, "resulted_at", require_str(self.resulted_at, "resulted_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
