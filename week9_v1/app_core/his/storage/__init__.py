from pathlib import Path

from .base import HisStorage, InMemoryHisStorage, StorageError
from .postgres import PostgresHisStorage
from .sqlite_dev import SQLiteDevHisStorage
from app_core.his.config import HIS_DB_BACKEND


def create_his_storage(
    *,
    backend: str | None = None,
    dsn: str = "",
    sqlite_path: str | Path | None = None,
) -> HisStorage:
    resolved = (backend or HIS_DB_BACKEND).strip().lower()
    if resolved == "memory":
        return InMemoryHisStorage()
    if resolved == "sqlite_dev":
        sqlite = SQLiteDevHisStorage(db_path=Path(sqlite_path)) if sqlite_path is not None else SQLiteDevHisStorage()
        sqlite.bootstrap()
        return sqlite
    if resolved == "postgres":
        postgres = PostgresHisStorage(dsn=dsn)
        postgres.bootstrap()
        return postgres.as_storage()
    raise StorageError(f"Unsupported HIS backend: {resolved}")

__all__ = [
    "HisStorage",
    "InMemoryHisStorage",
    "PostgresHisStorage",
    "SQLiteDevHisStorage",
    "StorageError",
    "create_his_storage",
]
