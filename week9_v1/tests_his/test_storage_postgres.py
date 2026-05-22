from pathlib import Path

from app_core.his.storage.postgres import PostgresHisStorage


def test_postgres_scaffold_bootstrap_requires_dsn() -> None:
    storage = PostgresHisStorage(dsn="postgresql://his:his@localhost:5432/his", migrations_dir=Path("sql/postgres"))

    migration_paths = storage.bootstrap()

    assert storage.migrations_dir == Path("sql/postgres")
    assert len(migration_paths) == 6
    assert migration_paths[0].name == "001_core_master_tables.sql"


def test_postgres_migration_sql_can_be_loaded() -> None:
    storage = PostgresHisStorage(dsn="postgresql://his:his@localhost:5432/his", migrations_dir=Path("sql/postgres"))

    sql_blocks = storage.load_migration_sql()

    assert len(sql_blocks) == 6
    assert "CREATE TABLE IF NOT EXISTS patients" in sql_blocks[0]


def test_core_migration_files_exist() -> None:
    root = Path(__file__).resolve().parents[1] / "sql" / "postgres"
    assert (root / "001_core_master_tables.sql").exists()
    assert (root / "002_encounter_tables.sql").exists()
    assert (root / "003_order_result_tables.sql").exists()
    assert (root / "004_document_event_tables.sql").exists()
    assert (root / "005_runtime_audit_tables.sql").exists()
    assert (root / "006_seed_dev_reference.sql").exists()
