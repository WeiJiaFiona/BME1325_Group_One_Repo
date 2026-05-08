from __future__ import annotations

from app_core.his.schemas import OrderRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def create_order(order: OrderRecord, storage: HisStorage | None = None) -> OrderRecord:
    return resolve_storage(storage).create_order(order)
