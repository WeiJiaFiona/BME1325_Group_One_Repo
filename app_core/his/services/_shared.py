from __future__ import annotations

from app_core.his.storage.base import HisStorage, InMemoryHisStorage

_DEFAULT_STORAGE = InMemoryHisStorage()


def resolve_storage(storage: HisStorage | None) -> HisStorage:
    return storage or _DEFAULT_STORAGE
