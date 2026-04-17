from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Dict, Optional
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from week5_system.app.schema import (
    ERROR_INVALID_STATE,
    ERROR_NOT_FOUND,
    PayloadError,
    error_response,
    validate_handoff_complete_payload,
    validate_handoff_request_payload,
)


HANDOFF_TIMEOUT_SECONDS = 1800


@dataclass
class HandoffRecord:
    handoff_ticket_id: str
    status: str
    patient_id: str
    acuity_ad: str
    zone: str
    stability: str
    required_unit: str
    clinical_summary: str
    pending_tasks: list
    requested_at: str
    receiver_system: str = ""
    accepted_at: str = ""
    receiver_bed: str = ""
    completed_at: str = ""
    reason: str = ""


_HANDOFFS: Dict[str, HandoffRecord] = {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _event(event: str, state: str = "", details: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    payload: Dict[str, object] = {"ts": _iso_now(), "event": event}
    if state:
        payload["state"] = state
    if details:
        payload["details"] = details
    return payload


def _call_mock_server(payload: Dict[str, object]) -> Optional[Dict[str, object]]:
    mock_url = os.environ.get("HANDOFF_MOCK_URL", "").strip()
    if not mock_url:
        return None
    data = json.dumps(payload).encode("utf-8")
    req = Request(mock_url, data=data, headers={"Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}))
    with opener.open(req, timeout=5) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def reset_store() -> None:
    _HANDOFFS.clear()


def request(payload: Dict[str, object]) -> Dict[str, object]:
    try:
        cleaned = validate_handoff_request_payload(payload)
    except PayloadError as exc:
        field_errors = []
        if exc.field:
            field_errors = [{"field": exc.field, "error_code": exc.error_code, "message": exc.message}]
        return error_response(exc.error_code, exc.message, field_errors=field_errors)

    handoff_ticket_id = f"handoff-{uuid4().hex[:8]}"
    status = "REQUESTED"
    reason = ""

    mock_resp = _call_mock_server(cleaned)
    if mock_resp is not None and not bool(mock_resp.get("accepted", True)):
        status = "REJECTED"
        reason = str(mock_resp.get("reason", "mock_rejected"))

    record = HandoffRecord(
        handoff_ticket_id=handoff_ticket_id,
        status=status,
        patient_id=cleaned["patient_id"],
        acuity_ad=cleaned["acuity_ad"],
        zone=cleaned["zone"],
        stability=cleaned["stability"],
        required_unit=cleaned["required_unit"],
        clinical_summary=cleaned["clinical_summary"],
        pending_tasks=cleaned["pending_tasks"],
        requested_at=_iso_now(),
        reason=reason,
    )
    _HANDOFFS[handoff_ticket_id] = record

    return {
        "handoff_ticket_id": handoff_ticket_id,
        "status": status,
        "reason": reason,
        "event_trace": [_event("handoff_requested", state=status)],
    }


def complete(payload: Dict[str, object]) -> Dict[str, object]:
    try:
        cleaned = validate_handoff_complete_payload(payload)
    except PayloadError as exc:
        field_errors = []
        if exc.field:
            field_errors = [{"field": exc.field, "error_code": exc.error_code, "message": exc.message}]
        return error_response(exc.error_code, exc.message, field_errors=field_errors)

    handoff_ticket_id = cleaned["handoff_ticket_id"]
    record = _HANDOFFS.get(handoff_ticket_id)
    if not record:
        return error_response(ERROR_NOT_FOUND, "handoff_ticket_id not found")

    if record.status != "REQUESTED":
        return error_response(ERROR_INVALID_STATE, "Invalid state transition")

    accepted_at_dt = cleaned["accepted_at_dt"]
    requested_at_dt = _parse_iso(record.requested_at)
    latency_seconds = max(0, int((accepted_at_dt - requested_at_dt).total_seconds()))

    final_state = "COMPLETED"
    if latency_seconds > HANDOFF_TIMEOUT_SECONDS:
        final_state = "TIMEOUT"
    elif cleaned["receiver_bed"] == "":
        final_state = "REJECTED"

    record.status = final_state
    record.receiver_system = cleaned["receiver_system"]
    record.accepted_at = cleaned["accepted_at"]
    record.receiver_bed = cleaned["receiver_bed"]
    record.completed_at = _iso_now()

    return {
        "final_disposition_state": final_state,
        "transfer_latency_seconds": latency_seconds,
        "event_trace": [_event("handoff_completed", state=final_state)],
    }


def get(handoff_ticket_id: str) -> Dict[str, object]:
    record = _HANDOFFS.get(handoff_ticket_id)
    if not record:
        return error_response(ERROR_NOT_FOUND, "handoff_ticket_id not found")
    return record.__dict__.copy()
