from __future__ import annotations

from typing import Any, Dict


def summarize_sync_result(result: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = dict(result or {})
    move = dict(payload.get("move") or {})
    ensure = dict(payload.get("ensure") or {})
    return {
        "ok": bool(payload.get("ok", False)),
        "skipped": bool(payload.get("skipped", False)),
        "stage": payload.get("stage"),
        "patient_id": payload.get("patient_id") or ensure.get("patientId") or ensure.get("patient_id"),
        "event_id": move.get("eventId") or move.get("event_id"),
        "accepted": move.get("accepted"),
        "reason_code": move.get("reasonCode") or ensure.get("reasonCode"),
        "event_seq": move.get("eventSeq") or move.get("event_seq"),
        "request_id": payload.get("request_id"),
    }
