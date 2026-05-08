from __future__ import annotations

from app_core.his.schemas import ClinicalDocumentRecord, DocumentRegistryEntry
from app_core.his.storage.base import HisStorage

from ._shared import resolve_storage


def register_document(
    document: ClinicalDocumentRecord,
    *,
    registry_entry: DocumentRegistryEntry | None = None,
    storage: HisStorage | None = None,
) -> tuple[ClinicalDocumentRecord, DocumentRegistryEntry | None]:
    backend = resolve_storage(storage)
    stored_document = backend.write_clinical_document(document)
    stored_registry = backend.register_document(registry_entry) if registry_entry is not None else None
    return stored_document, stored_registry
