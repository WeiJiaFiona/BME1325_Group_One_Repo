from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "runtime_data" / "memory"


def memory_v1_enabled() -> bool:
    value = os.environ.get("MEMORY_V1_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def get_runtime_root() -> Path:
    raw = os.environ.get("MEMORY_V1_ROOT", "").strip()
    return Path(raw) if raw else DEFAULT_RUNTIME_ROOT
