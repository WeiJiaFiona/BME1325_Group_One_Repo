from app_core.his.schemas import ClinicalDocumentRecord, DocumentRegistryEntry, EncounterRecord, PatientRecord
from app_core.his.services.document_registry_service import register_document
from app_core.his.services.encounter_service import open_encounter
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.storage.base import InMemoryHisStorage


def test_register_document_and_registry_entry() -> None:
    storage = InMemoryHisStorage()
    patient = register_patient(PatientRecord(full_name="Document Patient"), storage=storage)
    encounter = open_encounter(EncounterRecord(patient_id=patient.patient_id), storage=storage)
    document = ClinicalDocumentRecord(
        document_id="DOC-001",
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        document_type="handoff_note",
        content={"summary": "stable"},
    )
    registry_entry = DocumentRegistryEntry(
        registry_id="REG-001",
        document_id=document.document_id,
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        document_type=document.document_type,
        metadata={"source": "unit-test"},
    )

    stored_document, stored_registry = register_document(document, registry_entry=registry_entry, storage=storage)

    assert stored_document == document
    assert stored_registry == registry_entry
    assert storage.list_documents(encounter.encounter_id) == [document]
