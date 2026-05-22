from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app_core.his.config import generate_patient_id, utc_now_iso

from ._base import optional_str, require_dict, require_str


@dataclass(frozen=True)
class PatientRecord:
    patient_id: str = field(default_factory=generate_patient_id)
    mrn: Optional[str] = None
    full_name: str = "Unknown Patient"
    sex: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    identifiers: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "full_name", require_str(self.full_name, "full_name"))
        object.__setattr__(self, "mrn", optional_str(self.mrn, "mrn"))
        object.__setattr__(self, "sex", optional_str(self.sex, "sex"))
        object.__setattr__(self, "date_of_birth", optional_str(self.date_of_birth, "date_of_birth"))
        object.__setattr__(self, "phone", optional_str(self.phone, "phone"))
        object.__setattr__(self, "identifiers", require_dict(self.identifiers, "identifiers"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
