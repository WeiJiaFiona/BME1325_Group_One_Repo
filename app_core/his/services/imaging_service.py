from __future__ import annotations

from typing import Optional

from app_core.his.schemas import ImagingRequestRecord, ImagingResultRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def create_imaging_request(
    request: ImagingRequestRecord,
    storage: Optional[HisStorage] = None,
) -> ImagingRequestRecord:
    return resolve_storage(storage).create_imaging_request(request)


def record_imaging_result(
    result: ImagingResultRecord,
    storage: Optional[HisStorage] = None,
) -> ImagingResultRecord:
    return resolve_storage(storage).record_imaging_result(result)
