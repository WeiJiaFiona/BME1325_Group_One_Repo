from __future__ import annotations

from app_core.his.schemas import LabRequestRecord, LabResultRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def create_lab_request(request: LabRequestRecord, storage: HisStorage | None = None) -> LabRequestRecord:
    return resolve_storage(storage).create_lab_request(request)


def record_lab_result(result: LabResultRecord, storage: HisStorage | None = None) -> LabResultRecord:
    return resolve_storage(storage).record_lab_result(result)
