from pathlib import Path

from app_core.his.config import (
    EVENT_ENVELOPE_FIELDS,
    FROZEN_ROUTE_NAMES,
    POSTGRES_MIGRATION_SEQUENCE,
    generate_encounter_id,
    generate_patient_id,
)
from app_core.his.storage import create_his_storage
from app_core.his.schemas import EncounterRecord, PatientRecord
from app_core.his.services.encounter_service import get_encounter, open_encounter
from app_core.his.services.patient_registry_service import get_patient, register_patient
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage


def test_sqlite_dev_bootstrap_creates_local_placeholder(tmp_path: Path) -> None:
    db_path = tmp_path / "his_dev.sqlite3"
    storage = SQLiteDevHisStorage(db_path=db_path)

    boot_path = storage.bootstrap()

    assert boot_path == db_path
    assert db_path.exists()
    assert storage.as_storage() is not None


def test_contract_constants_are_frozen() -> None:
    assert generate_patient_id().startswith("P-")
    assert generate_encounter_id().startswith("E-")
    assert tuple(FROZEN_ROUTE_NAMES) == ("transfer", "admissions", "summary", "timeline")
    assert tuple(EVENT_ENVELOPE_FIELDS) == (
        "event_id",
        "event_type",
        "occurred_at",
        "patient_id",
        "encounter_id",
        "source",
        "payload",
    )
    assert len(POSTGRES_MIGRATION_SEQUENCE) == 6


def test_default_storage_factory_returns_sqlite_backend(tmp_path: Path) -> None:
    storage = create_his_storage(backend="sqlite_dev", sqlite_path=tmp_path / "factory.sqlite3")

    assert isinstance(storage, SQLiteDevHisStorage)


def test_sqlite_dev_persists_patient_and_encounter(tmp_path: Path) -> None:
    storage = SQLiteDevHisStorage(db_path=tmp_path / "persist.sqlite3")
    storage.bootstrap()
    patient = register_patient(PatientRecord(full_name="SQLite Patient"), storage=storage)
    encounter = open_encounter(EncounterRecord(patient_id=patient.patient_id), storage=storage)

    assert get_patient(patient.patient_id, storage=storage) == patient
    assert get_encounter(encounter.encounter_id, storage=storage) == encounter
