from __future__ import annotations

from .schema import AuditRecord
from .storage import MemoryStorage


class AuditTrail:
    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def append(self, record: AuditRecord) -> AuditRecord:
        self.storage.append_audit(record)
        return record
