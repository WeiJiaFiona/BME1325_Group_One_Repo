from __future__ import annotations

from typing import Optional

from app_core.his.schemas import LabRequestRecord, LabResultRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def create_lab_request(request: LabRequestRecord, storage: Optional[HisStorage] = None) -> LabRequestRecord:
    return resolve_storage(storage).create_lab_request(request)


def record_lab_result(result: LabResultRecord, storage: Optional[HisStorage] = None) -> LabResultRecord:
    return resolve_storage(storage).record_lab_result(result)
