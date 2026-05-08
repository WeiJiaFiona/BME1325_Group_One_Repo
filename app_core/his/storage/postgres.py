from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app_core.his.config import POSTGRES_MIGRATION_SEQUENCE

from .base import HisStorage, InMemoryHisStorage, StorageError


@dataclass
class PostgresHisStorage:
    dsn: str
    migrations_dir: Path | None = None
    apply_on_bootstrap: bool = False
    _delegate: InMemoryHisStorage | None = None

    def bootstrap(self) -> list[Path]:
        if not self.dsn.strip():
            raise StorageError("Postgres DSN is required")
        migration_paths = self.migration_paths()
        if self.apply_on_bootstrap:
            self._apply_migrations(migration_paths)
        return migration_paths

    def migration_paths(self) -> list[Path]:
        migrations_dir = self.migrations_dir or Path(__file__).resolve().parents[3] / "sql" / "postgres"
        paths: list[Path] = []
        for name in POSTGRES_MIGRATION_SEQUENCE:
            path = migrations_dir / name
            if not path.exists():
                raise StorageError(f"Missing migration file: {path}")
            paths.append(path)
        return paths

    def load_migration_sql(self) -> list[str]:
        return [path.read_text(encoding="utf-8") for path in self.migration_paths()]

    def as_storage(self) -> HisStorage:
        # PostgreSQL wiring is exposed through the same storage interface. Until
        # DB driver setup is provided in the deployment environment, keep the
        # substrate importable and callable via an in-memory delegate.
        if self._delegate is None:
            self._delegate = InMemoryHisStorage()
        return self._delegate

    def _apply_migrations(self, migration_paths: list[Path]) -> None:
        try:
            import psycopg  # type: ignore
        except ImportError:
            psycopg = None
        try:
            import psycopg2  # type: ignore
        except ImportError:
            psycopg2 = None

        if psycopg is None and psycopg2 is None:
            raise StorageError("Postgres driver not installed; cannot apply migrations")

        if psycopg is not None:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    for path in migration_paths:
                        cur.execute(path.read_text(encoding="utf-8"))
                conn.commit()
            return

        assert psycopg2 is not None
        conn = psycopg2.connect(self.dsn)
        try:
            cur = conn.cursor()
            for path in migration_paths:
                cur.execute(path.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()
