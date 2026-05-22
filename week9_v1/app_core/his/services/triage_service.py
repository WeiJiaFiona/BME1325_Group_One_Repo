from __future__ import annotations

from app_core.his.schemas import TriageRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def record_triage(triage: TriageRecord, storage: HisStorage | None = None) -> TriageRecord:
    return resolve_storage(storage).write_triage(triage)


def get_triage(encounter_id: str, storage: HisStorage | None = None) -> TriageRecord | None:
    return resolve_storage(storage).get_triage(encounter_id)
