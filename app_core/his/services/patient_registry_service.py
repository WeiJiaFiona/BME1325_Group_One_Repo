from __future__ import annotations

from typing import Optional

from app_core.his.schemas import PatientRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def register_patient(patient: PatientRecord, storage: Optional[HisStorage] = None) -> PatientRecord:
    return resolve_storage(storage).upsert_patient(patient)


def get_patient(patient_id: str, storage: Optional[HisStorage] = None) -> Optional[PatientRecord]:
    return resolve_storage(storage).get_patient(patient_id)
