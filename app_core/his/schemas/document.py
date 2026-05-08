from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import utc_now_iso

from ._base import require_dict, require_str


@dataclass(frozen=True)
class ClinicalDocumentRecord:
    document_id: str
    encounter_id: str
    patient_id: str
    document_type: str
    content: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", require_str(self.document_id, "document_id"))
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "document_type", require_str(self.document_type, "document_type"))
        object.__setattr__(self, "content", require_dict(self.content, "content"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentRegistryEntry:
    registry_id: str
    document_id: str
    encounter_id: str
    patient_id: str
    document_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "registry_id", require_str(self.registry_id, "registry_id"))
        object.__setattr__(self, "document_id", require_str(self.document_id, "document_id"))
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "document_type", require_str(self.document_type, "document_type"))
        object.__setattr__(self, "metadata", require_dict(self.metadata, "metadata"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
