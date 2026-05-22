from app_core.his.schemas import DepartmentRecord, ProviderRecord
from app_core.his.services import get_department, get_provider, register_department, register_provider
from app_core.his.storage.base import InMemoryHisStorage
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage


def test_provider_and_department_round_trip_in_memory() -> None:
    storage = InMemoryHisStorage()
    provider = ProviderRecord(provider_id="PROV-001", full_name="Dr Example", role="doctor", department_id="DEPT-ED")
    department = DepartmentRecord(department_id="DEPT-ED", department_name="Emergency", zone="red")

    stored_provider = register_provider(provider, storage=storage)
    stored_department = register_department(department, storage=storage)

    assert stored_provider == provider
    assert stored_department == department
    assert get_provider(provider.provider_id, storage=storage) == provider
    assert get_department(department.department_id, storage=storage) == department


def test_provider_and_department_round_trip_sqlite(tmp_path) -> None:
    storage = SQLiteDevHisStorage(db_path=tmp_path / "registries.sqlite3")
    storage.bootstrap()
    provider = ProviderRecord(provider_id="PROV-002", full_name="Nurse Example", role="triage_nurse", department_id="DEPT-OBS")
    department = DepartmentRecord(department_id="DEPT-OBS", department_name="Observation", zone="yellow")

    register_provider(provider, storage=storage)
    register_department(department, storage=storage)

    assert get_provider(provider.provider_id, storage=storage) == provider
    assert get_department(department.department_id, storage=storage) == department
