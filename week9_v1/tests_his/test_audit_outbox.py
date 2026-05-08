from app_core.his.exchange.event_publisher import publish_event
from app_core.his.schemas import AuditLogEntry, EncounterRecord, PatientRecord
from app_core.his.services.audit_service import append_audit_log, list_audit_logs
from app_core.his.services.encounter_service import open_encounter
from app_core.his.services.outbox_service import enqueue_outbox_event, list_outbox_events
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.storage.base import InMemoryHisStorage


def test_audit_and_outbox_round_trip() -> None:
    storage = InMemoryHisStorage()
    patient = register_patient(PatientRecord(full_name="Audit Patient"), storage=storage)
    encounter = open_encounter(EncounterRecord(patient_id=patient.patient_id), storage=storage)
    audit = AuditLogEntry(
        audit_id="AUD-001",
        action="encounter.open",
        actor="doctor",
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        details={"source": "tests"},
    )

    append_audit_log(audit, storage=storage)
    outbox = enqueue_outbox_event(
        event_type="encounter.opened",
        encounter_id=encounter.encounter_id,
        payload={"patient_id": patient.patient_id},
        storage=storage,
    )
    published = publish_event(outbox)

    assert list_audit_logs(encounter.encounter_id, storage=storage) == [audit]
    assert list_outbox_events(encounter.encounter_id, storage=storage) == [outbox]
    assert published["status"] == "DEFERRED"
