from __future__ import annotations

from typing import Optional

from app_core.his.schemas import HandoffSnapshotRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def write_handoff_snapshot(
    snapshot: HandoffSnapshotRecord,
    storage: Optional[HisStorage] = None,
) -> HandoffSnapshotRecord:
    return resolve_storage(storage).write_handoff_snapshot(snapshot)


def get_handoff_snapshots(
    encounter_id: str,
    storage: Optional[HisStorage] = None,
) -> list[HandoffSnapshotRecord]:
    return resolve_storage(storage).get_handoff_snapshots(encounter_id)
