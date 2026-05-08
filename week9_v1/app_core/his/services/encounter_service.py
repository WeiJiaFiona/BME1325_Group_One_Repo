from __future__ import annotations

from dataclasses import replace

from app_core.his.config import utc_now_iso
from app_core.his.schemas import (
    ClinicalAssessmentRecord,
    CurrentSummaryRecord,
    DiagnosisRecord,
    EncounterRecord,
    VitalSignsRecord,
)
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def open_encounter(encounter: EncounterRecord, storage: HisStorage | None = None) -> EncounterRecord:
    return resolve_storage(storage).create_encounter(encounter)


def get_encounter(encounter_id: str, storage: HisStorage | None = None) -> EncounterRecord | None:
    return resolve_storage(storage).get_encounter(encounter_id)


def update_encounter_state(
    encounter_id: str,
    *,
    status: str,
    current_zone: str | None = None,
    ctas_level: str | None = None,
    storage: HisStorage | None = None,
) -> EncounterRecord:
    backend = resolve_storage(storage)
    existing = backend.get_encounter(encounter_id)
    if existing is None:
        raise KeyError(f"Encounter not found: {encounter_id}")
    updated = replace(
        existing,
        status=status,
        current_zone=current_zone if current_zone is not None else existing.current_zone,
        ctas_level=ctas_level if ctas_level is not None else existing.ctas_level,
        updated_at=utc_now_iso(),
    )
    return backend.update_encounter(updated)


def record_vital_signs(vitals: VitalSignsRecord, storage: HisStorage | None = None) -> VitalSignsRecord:
    return resolve_storage(storage).append_vital_signs(vitals)


def record_clinical_assessment(
    assessment: ClinicalAssessmentRecord,
    storage: HisStorage | None = None,
) -> ClinicalAssessmentRecord:
    return resolve_storage(storage).append_clinical_assessment(assessment)


def record_diagnosis(diagnosis: DiagnosisRecord, storage: HisStorage | None = None) -> DiagnosisRecord:
    return resolve_storage(storage).append_diagnosis(diagnosis)


def write_current_summary(summary: CurrentSummaryRecord, storage: HisStorage | None = None) -> CurrentSummaryRecord:
    return resolve_storage(storage).write_current_summary(summary)


def get_current_summary(encounter_id: str, storage: HisStorage | None = None) -> CurrentSummaryRecord | None:
    return resolve_storage(storage).get_current_summary(encounter_id)
