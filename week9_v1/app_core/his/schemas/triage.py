from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import utc_now_iso

from ._base import require_dict, require_str


@dataclass(frozen=True)
class TriageRecord:
    encounter_id: str
    patient_id: str
    triage_id: str
    ctas_level: str
    zone: str
    summary: str = ""
    structured_data: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "triage_id", require_str(self.triage_id, "triage_id"))
        object.__setattr__(self, "ctas_level", require_str(self.ctas_level, "ctas_level"))
        object.__setattr__(self, "zone", require_str(self.zone, "zone"))
        object.__setattr__(self, "summary", self.summary.strip())
        object.__setattr__(self, "structured_data", require_dict(self.structured_data, "structured_data"))
        object.__setattr__(self, "recorded_at", require_str(self.recorded_at, "recorded_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
