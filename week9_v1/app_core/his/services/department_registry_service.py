from __future__ import annotations

from app_core.his.schemas import DepartmentRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def register_department(department: DepartmentRecord, storage: HisStorage | None = None) -> DepartmentRecord:
    return resolve_storage(storage).upsert_department(department)


def get_department(department_id: str, storage: HisStorage | None = None) -> DepartmentRecord | None:
    return resolve_storage(storage).get_department(department_id)
