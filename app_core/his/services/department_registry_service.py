from __future__ import annotations

from typing import Optional

from app_core.his.schemas import DepartmentRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def register_department(department: DepartmentRecord, storage: Optional[HisStorage] = None) -> DepartmentRecord:
    return resolve_storage(storage).upsert_department(department)


def get_department(department_id: str, storage: Optional[HisStorage] = None) -> Optional[DepartmentRecord]:
    return resolve_storage(storage).get_department(department_id)
