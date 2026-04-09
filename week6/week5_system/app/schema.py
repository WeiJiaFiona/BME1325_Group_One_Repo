from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


ERROR_INVALID_SCHEMA = "INVALID_SCHEMA"
ERROR_MISSING_FIELD = "MISSING_FIELD"
ERROR_INVALID_TYPE = "INVALID_TYPE"
ERROR_NOT_FOUND = "NOT_FOUND"
ERROR_INVALID_STATE = "INVALID_STATE"


@dataclass
class FieldError:
    field: str
    error_code: str
    message: str


class PayloadError(ValueError):
    def __init__(self, error_code: str, message: str, field: str = "") -> None:
        super().__init__(message)
        self.error_code = error_code
        self.field = field
        self.message = message


def error_response(error_code: str, message: str, field_errors: Optional[List[Any]] = None) -> Dict[str, Any]:
    normalized = []
    for item in field_errors or []:
        if isinstance(item, dict):
            normalized.append(item)
        elif hasattr(item, "__dict__"):
            normalized.append(item.__dict__)
    return {
        "error_code": error_code,
        "message": message,
        "field_errors": normalized,
    }


def _ensure_dict(payload: Any, name: str = "payload") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise PayloadError(ERROR_INVALID_SCHEMA, f"Invalid {name}: expected object")
    return payload


def _require_key(payload: Dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise PayloadError(ERROR_MISSING_FIELD, f"Missing field: {key}", field=key)
    return payload[key]


def _require_str(payload: Dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = _require_key(payload, key)
    if not isinstance(value, str):
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected string", field=key)
    if not allow_empty and not value.strip():
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: empty string", field=key)
    return value


def _optional_str(payload: Dict[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected string", field=key)
    return value


def _require_list_of_str(payload: Dict[str, Any], key: str, *, allow_empty: bool = True) -> List[str]:
    value = _require_key(payload, key)
    if not isinstance(value, list):
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected list", field=key)
    if not allow_empty and len(value) == 0:
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: empty list", field=key)
    result: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected list[str]", field=key)
        result.append(item)
    return result


def _optional_list_of_str(payload: Dict[str, Any], key: str, default: Optional[List[str]] = None) -> List[str]:
    if key not in payload:
        return list(default or [])
    value = payload.get(key)
    if not isinstance(value, list):
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected list", field=key)
    result: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected list[str]", field=key)
        result.append(item)
    return result


def _require_dict(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = _require_key(payload, key)
    if not isinstance(value, dict):
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {key}: expected object", field=key)
    return value


def _validate_vitals(vitals: Dict[str, Any]) -> Dict[str, float]:
    if "spo2" not in vitals:
        raise PayloadError(ERROR_MISSING_FIELD, "Missing field: vitals.spo2", field="vitals.spo2")
    if "sbp" not in vitals:
        raise PayloadError(ERROR_MISSING_FIELD, "Missing field: vitals.sbp", field="vitals.sbp")

    cleaned: Dict[str, float] = {}
    for name, value in vitals.items():
        if not isinstance(value, (int, float)):
            raise PayloadError(ERROR_INVALID_TYPE, f"Invalid vitals.{name}: expected number", field=f"vitals.{name}")
        cleaned[name] = float(value)

    if not (0 <= cleaned.get("spo2", 0) <= 100):
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid vitals.spo2: out of range", field="vitals.spo2")
    if cleaned.get("sbp", 0) <= 0:
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid vitals.sbp: out of range", field="vitals.sbp")

    return cleaned


def _validate_arrival_mode(value: str) -> str:
    if value not in {"walk-in", "ambulance"}:
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid arrival_mode: expected walk-in or ambulance", field="arrival_mode")
    return value


def validate_encounter_start_payload(payload: Any) -> Dict[str, Any]:
    payload = _ensure_dict(payload)
    chief_complaint = _require_str(payload, "chief_complaint")
    symptoms = _optional_list_of_str(payload, "symptoms", default=[])
    vitals = _validate_vitals(_require_dict(payload, "vitals"))
    arrival_mode = _optional_str(payload, "arrival_mode", default="walk-in")
    arrival_mode = _validate_arrival_mode(arrival_mode)
    patient_id = _optional_str(payload, "patient_id", default="patient-unknown")
    return {
        "patient_id": patient_id,
        "chief_complaint": chief_complaint,
        "symptoms": symptoms,
        "vitals": vitals,
        "arrival_mode": arrival_mode,
    }


def validate_handoff_request_payload(payload: Any) -> Dict[str, Any]:
    payload = _ensure_dict(payload)
    patient_id = _require_str(payload, "patient_id")
    acuity_ad = _require_str(payload, "acuity_ad")
    if acuity_ad not in {"A", "B", "C", "D"}:
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid acuity_ad: expected A/B/C/D", field="acuity_ad")

    zone = _require_str(payload, "zone")
    if zone not in {"red", "yellow", "green"}:
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid zone: expected red/yellow/green", field="zone")

    stability = _require_str(payload, "stability")
    if stability not in {"stable", "unstable", "critical"}:
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid stability: expected stable/unstable/critical", field="stability")

    required_unit = _require_str(payload, "required_unit")
    if required_unit not in {"ICU", "WARD"}:
        raise PayloadError(ERROR_INVALID_TYPE, "Invalid required_unit: expected ICU or WARD", field="required_unit")

    clinical_summary = _require_str(payload, "clinical_summary")
    pending_tasks = _require_list_of_str(payload, "pending_tasks", allow_empty=True)

    return {
        "patient_id": patient_id,
        "acuity_ad": acuity_ad,
        "zone": zone,
        "stability": stability,
        "required_unit": required_unit,
        "clinical_summary": clinical_summary,
        "pending_tasks": pending_tasks,
    }


def _parse_iso8601(value: str, field: str) -> datetime:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise PayloadError(ERROR_INVALID_TYPE, f"Invalid {field}: expected ISO-8601", field=field) from exc


def validate_handoff_complete_payload(payload: Any) -> Dict[str, Any]:
    payload = _ensure_dict(payload)
    handoff_ticket_id = _require_str(payload, "handoff_ticket_id")
    receiver_system = _require_str(payload, "receiver_system")
    accepted_at = _require_str(payload, "accepted_at")
    receiver_bed = _require_str(payload, "receiver_bed", allow_empty=True)

    accepted_at_dt = _parse_iso8601(accepted_at, "accepted_at")

    return {
        "handoff_ticket_id": handoff_ticket_id,
        "receiver_system": receiver_system,
        "accepted_at": accepted_at,
        "accepted_at_dt": accepted_at_dt,
        "receiver_bed": receiver_bed,
    }
