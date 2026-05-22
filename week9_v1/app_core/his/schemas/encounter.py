from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import generate_encounter_id, utc_now_iso

from ._base import ensure_list_of_dicts, optional_str, require_dict, require_str


@dataclass(frozen=True)
class EncounterRecord:
    patient_id: str
    encounter_id: str = field(default_factory=generate_encounter_id)
    status: str = "OPEN"
    arrival_mode: str = "walk-in"
    current_zone: str | None = None
    ctas_level: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "status", require_str(self.status, "status"))
        object.__setattr__(self, "arrival_mode", require_str(self.arrival_mode, "arrival_mode"))
        object.__setattr__(self, "current_zone", optional_str(self.current_zone, "current_zone"))
        object.__setattr__(self, "ctas_level", optional_str(self.ctas_level, "ctas_level"))
        object.__setattr__(self, "metadata", require_dict(self.metadata, "metadata"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", require_str(self.updated_at, "updated_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VitalSignsRecord:
    encounter_id: str
    patient_id: str
    vital_id: str
    readings: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "vital_id", require_str(self.vital_id, "vital_id"))
        object.__setattr__(self, "readings", require_dict(self.readings, "readings"))
        object.__setattr__(self, "recorded_at", require_str(self.recorded_at, "recorded_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClinicalAssessmentRecord:
    encounter_id: str
    patient_id: str
    assessment_id: str
    author_role: str
    findings: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "assessment_id", require_str(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "author_role", require_str(self.author_role, "author_role"))
        object.__setattr__(self, "findings", require_dict(self.findings, "findings"))
        object.__setattr__(self, "recorded_at", require_str(self.recorded_at, "recorded_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosisRecord:
    encounter_id: str
    patient_id: str
    diagnosis_id: str
    label: str
    diagnosis_type: str = "working"
    details: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "diagnosis_id", require_str(self.diagnosis_id, "diagnosis_id"))
        object.__setattr__(self, "label", require_str(self.label, "label"))
        object.__setattr__(self, "diagnosis_type", require_str(self.diagnosis_type, "diagnosis_type"))
        object.__setattr__(self, "details", require_dict(self.details, "details"))
        object.__setattr__(self, "recorded_at", require_str(self.recorded_at, "recorded_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CurrentSummaryRecord:
    encounter_id: str
    patient_id: str
    summary_id: str
    current_state: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_memory_ids: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "summary_id", require_str(self.summary_id, "summary_id"))
        object.__setattr__(self, "current_state", require_str(self.current_state, "current_state"))
        object.__setattr__(self, "payload", require_dict(self.payload, "payload"))
        object.__setattr__(self, "source_memory_ids", ensure_list_of_dicts(self.source_memory_ids, "source_memory_ids"))
        object.__setattr__(self, "updated_at", require_str(self.updated_at, "updated_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
