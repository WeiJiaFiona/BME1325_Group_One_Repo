from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import Any, Dict


def _safe_len(value: Any) -> int:
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return 0


def _iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def queue_snapshot(maze: Any = None) -> Dict[str, object]:
    if maze is None:
        return {
            "queues": {
                "triage": {"size": 0, "avg_wait_seconds": 0},
                "doctor": {"size": 0, "avg_wait_seconds": 0},
                "test": {"size": 0, "avg_wait_seconds": 0},
                "boarding": {"size": 0, "avg_wait_seconds": 0},
            },
            "occupancy": {
                "beds_total": 0,
                "beds_occupied": 0,
                "beds_available": 0,
                "by_zone": {},
            },
            "snapshot_time": _iso_now(),
            "trace_id": f"trace-{uuid4().hex[:8]}",
        }

    triage_queue = _safe_len(getattr(maze, "triage_queue", []))
    doctor_queue = _safe_len(getattr(maze, "patients_waiting_for_doctor", []))

    queues = {
        "triage": {"size": triage_queue, "avg_wait_seconds": 0},
        "doctor": {"size": doctor_queue, "avg_wait_seconds": 0},
        "test": {"size": 0, "avg_wait_seconds": 0},
        "boarding": {"size": 0, "avg_wait_seconds": 0},
    }

    beds_total = 0
    beds_available = 0
    by_zone: Dict[str, Dict[str, int]] = {}

    injuries_zones = getattr(maze, "injuries_zones", {})
    if isinstance(injuries_zones, dict):
        for zone, info in injuries_zones.items():
            if not isinstance(info, dict):
                continue
            capacity = int(info.get("capacity", 0)) if isinstance(info.get("capacity", 0), int) else 0
            available = _safe_len(info.get("available_beds", []))
            occupied = max(0, capacity - available)
            by_zone[zone] = {"occupied": occupied, "available": available}
            beds_total += capacity
            beds_available += available

    beds_occupied = max(0, beds_total - beds_available)

    return {
        "queues": queues,
        "occupancy": {
            "beds_total": beds_total,
            "beds_occupied": beds_occupied,
            "beds_available": beds_available,
            "by_zone": by_zone,
        },
        "snapshot_time": _iso_now(),
        "trace_id": f"trace-{uuid4().hex[:8]}",
    }
