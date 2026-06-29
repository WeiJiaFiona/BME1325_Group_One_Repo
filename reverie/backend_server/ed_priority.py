from __future__ import annotations

from typing import Any


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def patient_ctas_level(patient: Any) -> int:
    scratch = getattr(patient, "scratch", None)
    if scratch is None:
        return 99
    return _coerce_int(getattr(scratch, "CTAS", None), 99)


def patient_arrival_minute(patient: Any) -> float:
    scratch = getattr(patient, "scratch", None)
    if scratch is None:
        return 999999.0
    return _coerce_float(getattr(scratch, "ed_arrival_minute", None), 999999.0)


def patient_triage_complete_minute(patient: Any) -> float:
    scratch = getattr(patient, "scratch", None)
    if scratch is None:
        return 999999.0
    return _coerce_float(getattr(scratch, "triage_completed_minute", None), 999999.0)


def patient_identity_key(patient: Any) -> str:
    return str(getattr(patient, "name", "") or "~unknown")


def ed_patient_priority_key(patient: Any) -> tuple[int, float, float, str]:
    return (
        patient_ctas_level(patient),
        patient_arrival_minute(patient),
        patient_triage_complete_minute(patient),
        patient_identity_key(patient),
    )


def queue_patient_priority_key(patient_name: str, personas: dict[str, Any]) -> tuple[int, float, float, str]:
    patient = personas.get(str(patient_name))
    if patient is None:
        return (999, 999999.0, 999999.0, str(patient_name))
    return ed_patient_priority_key(patient)


def queue_entry_priority_key(entry: Any, personas: dict[str, Any]) -> tuple[int, float, float, str]:
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return queue_patient_priority_key(str(entry[1]), personas)
    return (999, 999999.0, 999999.0, str(entry))
