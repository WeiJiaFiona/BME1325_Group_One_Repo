from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Optional
import uuid

ID_PREFIX_PATIENT = "P"
ID_PREFIX_ENCOUNTER = "E"
CN_TZ = timezone(timedelta(hours=8))
FROZEN_ROUTE_NAMES = ("transfer", "admissions", "summary", "timeline")
EVENT_ENVELOPE_FIELDS = (
    "event_id",
    "event_type",
    "occurred_at",
    "patient_id",
    "encounter_id",
    "source",
    "payload",
)
POSTGRES_MIGRATION_SEQUENCE = (
    "001_core_master_tables.sql",
    "002_encounter_tables.sql",
    "003_order_result_tables.sql",
    "004_document_event_tables.sql",
    "005_runtime_audit_tables.sql",
    "006_seed_dev_reference.sql",
)
HIS_DB_BACKEND = os.getenv("HIS_DB_BACKEND", "sqlite_dev").strip() or "sqlite_dev"
DEFAULT_SQLITE_DEV_PATH = os.getenv(
    "HIS_SQLITE_DEV_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "his_dev.sqlite3"),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_patient_id() -> str:
    return f"{ID_PREFIX_PATIENT}-{uuid.uuid4().hex[:8]}"


def generate_encounter_id(now: Optional[datetime] = None) -> str:
    if now is None:
        instant = datetime.now(CN_TZ)
    elif now.tzinfo is None:
        instant = now.replace(tzinfo=CN_TZ)
    else:
        instant = now.astimezone(CN_TZ)
    return f"{ID_PREFIX_ENCOUNTER}-{instant.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
