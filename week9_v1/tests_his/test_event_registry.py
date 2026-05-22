from app_core.his.config import utc_now_iso
from app_core.his.schemas import EncounterRecord, EventRegistryEntry, PatientRecord
from app_core.his.services.encounter_service import open_encounter
from app_core.his.services.event_registry_service import append_event_registry_entry, list_event_registry_entries
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.storage.base import InMemoryHisStorage


def test_event_registry_round_trip() -> None:
    storage = InMemoryHisStorage()
    patient = register_patient(PatientRecord(full_name="Event Patient"), storage=storage)
    encounter = open_encounter(EncounterRecord(patient_id=patient.patient_id), storage=storage)
    event = EventRegistryEntry(
        event_id="EVT-001",
        event_type="triage.completed",
        occurred_at=utc_now_iso(),
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        source="tests",
        payload={"ctas_level": "L3"},
        tags=["triage"],
    )

    stored = append_event_registry_entry(event, storage=storage)

    assert stored == event
    assert list_event_registry_entries(encounter.encounter_id, storage=storage) == [event]
