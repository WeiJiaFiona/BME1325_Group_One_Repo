from app_core.his.schemas import EncounterRecord, PatientRecord
from app_core.his.services.encounter_service import get_encounter, open_encounter, update_encounter_state
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.storage.base import InMemoryHisStorage


def test_open_and_update_encounter() -> None:
    storage = InMemoryHisStorage()
    patient = register_patient(PatientRecord(full_name="Bob Example"), storage=storage)
    encounter = EncounterRecord(patient_id=patient.patient_id)

    opened = open_encounter(encounter, storage=storage)
    updated = update_encounter_state(
        opened.encounter_id,
        status="UNDER_EVALUATION",
        current_zone="red",
        ctas_level="L2",
        storage=storage,
    )

    assert opened.encounter_id.startswith("E-")
    assert get_encounter(opened.encounter_id, storage=storage) == updated
    assert updated.current_zone == "red"
    assert updated.ctas_level == "L2"
