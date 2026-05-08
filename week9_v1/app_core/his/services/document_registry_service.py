from __future__ import annotations

from app_core.his.schemas import ClinicalDocumentRecord, DocumentRegistryEntry


def register_document(
    document: ClinicalDocumentRecord,
    registry_entry: DocumentRegistryEntry | None = None,
) -> tuple[ClinicalDocumentRecord, DocumentRegistryEntry | None]:
    return document, registry_entry
