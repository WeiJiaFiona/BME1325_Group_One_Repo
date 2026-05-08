from pathlib import Path

from app_core.his.storage.postgres import PostgresHisStorage


def test_postgres_scaffold_bootstrap_requires_dsn() -> None:
    storage = PostgresHisStorage(dsn="postgresql://his:his@localhost:5432/his", migrations_dir=Path("sql/postgres"))

    storage.bootstrap()

    assert storage.migrations_dir == Path("sql/postgres")


def test_core_migration_files_exist() -> None:
    root = Path("/home/jiawei2022/BME1325/week9/week9_v1/sql/postgres")
    assert (root / "001_core_master_tables.sql").exists()
    assert (root / "002_encounter_tables.sql").exists()
    assert (root / "003_order_result_tables.sql").exists()
