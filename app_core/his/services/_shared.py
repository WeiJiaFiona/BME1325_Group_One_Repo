from __future__ import annotations

from typing import Optional

from app_core.his.storage.base import HisStorage, InMemoryHisStorage

_DEFAULT_STORAGE = InMemoryHisStorage()


def resolve_storage(storage: Optional[HisStorage]) -> HisStorage:
    return storage or _DEFAULT_STORAGE
