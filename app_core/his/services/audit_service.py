from __future__ import annotations

from typing import Optional

from app_core.his.schemas import AuditLogEntry
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def append_audit_log(entry: AuditLogEntry, storage: Optional[HisStorage] = None) -> AuditLogEntry:
    return resolve_storage(storage).append_audit(entry)


def list_audit_logs(
    encounter_id: Optional[str] = None,
    storage: Optional[HisStorage] = None,
) -> list[AuditLogEntry]:
    return resolve_storage(storage).list_audits(encounter_id)
