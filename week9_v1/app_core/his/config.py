from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid

ID_PREFIX_PATIENT = "P"
ID_PREFIX_ENCOUNTER = "E"
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
HIS_DB_BACKEND = os.getenv("HIS_DB_BACKEND", "sqlite_dev").strip() or "sqlite_dev"
DEFAULT_SQLITE_DEV_PATH = os.getenv(
    "HIS_SQLITE_DEV_PATH",
    "/home/jiawei2022/BME1325/week9/week9_v1/data/his_dev.sqlite3",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_patient_id() -> str:
    return f"{ID_PREFIX_PATIENT}-{uuid.uuid4().hex[:8]}"


def generate_encounter_id(now: datetime | None = None) -> str:
    instant = now.astimezone(timezone.utc) if now and now.tzinfo else now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return f"{ID_PREFIX_ENCOUNTER}-{instant.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
