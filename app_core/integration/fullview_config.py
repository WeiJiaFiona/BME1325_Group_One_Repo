from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / "runtime_data" / "fullview"


@dataclass(frozen=True)
class FullViewConfig:
    enabled: bool
    base_url: str
    timeout_sec: float
    source: str
    operator_id: str
    runtime_root: Path


def load_fullview_config() -> FullViewConfig:
    enabled = str(os.getenv("FULLVIEW_SYNC_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "on"}
    base_url = str(os.getenv("FULLVIEW_BASE_URL", "http://127.0.0.1:8000")).strip().rstrip("/")
    timeout_sec = float(os.getenv("FULLVIEW_TIMEOUT_SEC", "5"))
    source = str(os.getenv("FULLVIEW_SOURCE", "edmas")).strip() or "edmas"
    operator_id = str(os.getenv("FULLVIEW_OPERATOR_ID", "edmas-adapter")).strip() or "edmas-adapter"
    runtime_root = Path(os.getenv("FULLVIEW_RUNTIME_DIR", str(RUNTIME_ROOT)))
    return FullViewConfig(
        enabled=enabled,
        base_url=base_url,
        timeout_sec=timeout_sec,
        source=source,
        operator_id=operator_id,
        runtime_root=runtime_root,
    )
