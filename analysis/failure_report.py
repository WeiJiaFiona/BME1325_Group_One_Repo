from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[1]
BACKEND_DIR = REPO_ROOT / "reverie" / "backend_server"
for _path in (str(REPO_ROOT), str(BACKEND_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from failure_metrics import collect_failure_metrics


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_failure_report(sim_dir: str | Path, output_path: str | Path | None = None) -> dict:
    sim_dir = Path(sim_dir)
    sim_status_path = sim_dir / "sim_status.json"
    data_collection_path = sim_dir / "reverie" / "data_collection.json"
    fallback_data_collection_path = sim_dir / "data_collection.json"

    sim_status = _load_json(sim_status_path, default={}) or {}
    data_collection = _load_json(data_collection_path, default=None)
    if data_collection is None:
        data_collection = _load_json(fallback_data_collection_path, default=None)

    if data_collection is not None:
        failure_metrics = collect_failure_metrics(
            personas={},
            maze=None,
            data_collection=data_collection,
            meta={},
            curr_time=None,
            curr_step=int(sim_status.get("step", 0) or 0),
        )
        report = {
            "arrivals_total": int(failure_metrics.get("total_arrived_patients", 0) or 0),
            "failed_patients_count": int(failure_metrics.get("failed_patients_count", 0) or 0),
            "failure_rate": float(failure_metrics.get("failure_rate", 0.0) or 0.0),
            "system_failed": bool(failure_metrics.get("system_failed", False)),
            "failure_threshold": float(failure_metrics.get("failure_threshold", 0.1) or 0.1),
            "system_failed_comparator": failure_metrics.get("system_failed_comparator", "gt"),
            "failed_patients": list(failure_metrics.get("failed_patients", []) or []),
            "failure_reasons_by_patient": dict(failure_metrics.get("failure_reasons_by_patient", {}) or {}),
            "failed_at_step": dict(failure_metrics.get("failed_at_step", {}) or {}),
            "failure_reason_counts": dict(failure_metrics.get("failure_reason_counts", {}) or {}),
            "patient_level_detail_available": True,
        }
    else:
        resources = sim_status.get("resources", {}) if isinstance(sim_status, dict) else {}
        report = {
            "arrivals_total": int(resources.get("total_arrived_patients", 0) or 0),
            "failed_patients_count": int(resources.get("failed_patients_count", 0) or 0),
            "failure_rate": float(resources.get("failure_rate", 0.0) or 0.0),
            "system_failed": bool(resources.get("system_failed", False)),
            "failure_threshold": float(resources.get("failure_threshold", 0.1) or 0.1),
            "system_failed_comparator": resources.get("system_failed_comparator", "gt"),
            "failed_patients": [],
            "failure_reasons_by_patient": {},
            "failed_at_step": {},
            "failure_reason_counts": dict(resources.get("failure_reason_counts", {}) or {}),
            "patient_level_detail_available": False,
        }

    if output_path is None:
        output_path = sim_dir / "analysis" / "failure_report.json"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report
