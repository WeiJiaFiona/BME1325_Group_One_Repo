from __future__ import annotations

from typing import Optional

from app_core.his.schemas import ProviderRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def register_provider(provider: ProviderRecord, storage: Optional[HisStorage] = None) -> ProviderRecord:
    return resolve_storage(storage).upsert_provider(provider)


def get_provider(provider_id: str, storage: Optional[HisStorage] = None) -> Optional[ProviderRecord]:
    return resolve_storage(storage).get_provider(provider_id)
