from __future__ import annotations

from typing import Any, Dict


USER_PHASE_ROOM_MAP = {
    "INTAKE": "ed_registration",
    "CALL_NURSE_MEASURE": "ed_triage",
    "WAITING_CALL": "ed_waiting",
    "DOCTOR_CALLED": "ed_doctor_room",
    "BED_NURSE_FLOW": "ed_handoff",
    "DONE": "ed_entrance",
}

AUTO_ZONE_ROOM_MAP = {
    "waiting room": "ed_waiting",
    "waiting room chair": "ed_waiting",
    "diagnostic room": "ed_diagnostic",
    "trauma room": "ed_trauma",
    "major injuries zone": "ed_major",
    "minor injuries zone": "ed_minor",
}


def map_user_phase_to_room(*, phase: str, acuity: str | None) -> str:
    phase_value = str(phase or "").strip().upper()
    if phase_value == "DOCTOR_CALLED":
        if acuity in {"A", "B"}:
            return "ed_red_resus"
        if acuity == "C":
            return "ed_major"
        return "ed_doctor_room"
    return USER_PHASE_ROOM_MAP.get(phase_value, "ed_waiting")


def map_auto_location_to_room(*, zone: str | None, next_room: str | None, state: str | None, ctas: Any) -> str:
    next_room_value = str(next_room or "").strip().lower()
    if next_room_value in AUTO_ZONE_ROOM_MAP:
        return AUTO_ZONE_ROOM_MAP[next_room_value]
    zone_value = str(zone or "").strip().lower()
    if zone_value in AUTO_ZONE_ROOM_MAP:
        return AUTO_ZONE_ROOM_MAP[zone_value]
    ctas_level = safe_int(ctas, 3)
    if ctas_level <= 1:
        return "ed_red_resus"
    if ctas_level == 2:
        return "ed_major"
    if state == "WAITING_FOR_TEST":
        return "ed_diagnostic"
    return "ed_minor"


def build_sync_context(base: Dict[str, Any] | None, **extra: Any) -> Dict[str, Any]:
    context = dict(base or {})
    for key, value in extra.items():
        if value is not None and value != "":
            context[key] = value
    return context


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
