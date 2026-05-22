from __future__ import annotations

from typing import Optional

from app_core.his.schemas import OrderRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def create_order(order: OrderRecord, storage: Optional[HisStorage] = None) -> OrderRecord:
    return resolve_storage(storage).create_order(order)
