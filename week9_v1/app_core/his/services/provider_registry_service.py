from __future__ import annotations

from app_core.his.schemas import ProviderRecord
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def register_provider(provider: ProviderRecord, storage: HisStorage | None = None) -> ProviderRecord:
    return resolve_storage(storage).upsert_provider(provider)


def get_provider(provider_id: str, storage: HisStorage | None = None) -> ProviderRecord | None:
    return resolve_storage(storage).get_provider(provider_id)
