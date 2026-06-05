from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TransferRequest:
    transfer_id: str
    encounter_id: str
    patient_id: str
    from_group: str
    to_group: str
    from_unit: str
    to_unit: str
    request_step: int
    request_minute: int
    ctas_level: int | None = None
    reason: str | None = None
    summary: str | None = None
    requested_resources: list[str] = field(default_factory=list)
    status: str = "requested"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TransferResponse:
    transfer_id: str
    accepted: bool
    status: str
    reason: str | None = None
    assigned_bed: str | None = None
    available_capacity: int = 0
    expected_eta_minutes: int | None = None
    retry_after_seconds: int | None = None
    next_check_minute: int | None = None
    next_check_step: int | None = None
    transfer_completed_minute: int | None = None
    transfer_completed_step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
