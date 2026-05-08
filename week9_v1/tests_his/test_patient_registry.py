from app_core.his.schemas import PatientRecord
from app_core.his.services.patient_registry_service import get_patient, register_patient
from app_core.his.storage.base import InMemoryHisStorage


def test_register_and_get_patient_round_trip() -> None:
    storage = InMemoryHisStorage()
    patient = PatientRecord(full_name="Alice Example")

    stored = register_patient(patient, storage=storage)

    assert stored.patient_id.startswith("P-")
    assert get_patient(stored.patient_id, storage=storage) == stored
