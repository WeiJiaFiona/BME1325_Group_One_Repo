from pathlib import Path

from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES, generate_encounter_id, generate_patient_id
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
