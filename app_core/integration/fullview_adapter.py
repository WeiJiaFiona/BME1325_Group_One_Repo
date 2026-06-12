from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import hashlib
import json

from app_core.integration.disposition_rules import FullViewDecision
from app_core.integration.fullview_client import FullViewClient, find_patient_in_snapshot
from app_core.integration.fullview_config import load_fullview_config
from app_core.integration.fullview_mapping import build_sync_context


def sync_user_decision_to_fullview(
    *,
    patient_id: str,
    encounter_id: str,
    patient_name: str,
    chief_complaint: str,
    vitals: Dict[str, Any],
    ctas_level: Any,
    acuity: str | None,
    current_room_id: str,
    decision: FullViewDecision,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ensure_payload = {
        "source": "edmas",
        "external_patient_id": patient_id,
        "external_case_id": encounter_id,
        "department": "emergency",
        "name": patient_name,
        "chief_complaint": chief_complaint,
        "ctas_level": ctas_level,
        "acuity": acuity,
        "current_fullview_room_id": current_room_id,
        "status": "IN_TREATMENT",
        "context": build_sync_context(
            context,
            source="edmas",
            edmas_case_id=encounter_id,
            edmas_patient_name=patient_name,
            chief_complaint=chief_complaint,
            ctas_level=ctas_level,
            acuity=acuity,
            current_edmas_location=current_room_id,
            sync_reason=decision.sync_reason,
        ),
    }
    return _sync_to_fullview(
        ensure_payload=ensure_payload,
        decision=decision,
        explicit_from_room_id=current_room_id,
    )


def sync_auto_decision_to_fullview(
    *,
    patient_id: str,
    encounter_id: str,
    patient_name: str,
    chief_complaint: str,
    vitals: Dict[str, Any],
    ctas_level: Any,
    acuity: str | None,
    current_room_id: str,
    decision: FullViewDecision,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ensure_payload = {
        "source": "edmas",
        "external_patient_id": patient_id,
        "external_case_id": encounter_id,
        "department": "emergency",
        "name": patient_name,
        "chief_complaint": chief_complaint,
        "ctas_level": ctas_level,
        "acuity": acuity,
        "current_fullview_room_id": current_room_id,
        "status": "IN_TREATMENT",
        "context": build_sync_context(
            context,
            source="edmas",
            edmas_case_id=encounter_id,
            edmas_patient_name=patient_name,
            chief_complaint=chief_complaint,
            ctas_level=ctas_level,
            acuity=acuity,
            current_edmas_location=current_room_id,
            sync_reason=decision.sync_reason,
        ),
    }
    return _sync_to_fullview(
        ensure_payload=ensure_payload,
        decision=decision,
        explicit_from_room_id=current_room_id,
    )


def _sync_to_fullview(*, ensure_payload: Dict[str, Any], decision: FullViewDecision, explicit_from_room_id: str) -> Dict[str, Any]:
    config = load_fullview_config()
    if not config.enabled:
        return {"ok": True, "skipped": True, "reason": "FULLVIEW_SYNC_DISABLED"}

    client = FullViewClient(config)
    ensure_response = client.ensure_patient(ensure_payload)
    if not ensure_response.get("accepted", False):
        result = {
            "ok": False,
            "stage": "ensure_patient",
            "ensure": ensure_response,
            "move": None,
        }
        _append_adapter_log(config.runtime_root, result)
        return result

    ensured_patient = dict(ensure_response.get("patient") or {})
    canonical_patient_id = str(
        ensure_response.get("patientId")
        or ensure_response.get("patient_id")
        or ensured_patient.get("patientId")
        or ensure_payload.get("external_patient_id")
    ).strip()

    snapshot = client.get_snapshot()
    snapshot_patient = find_patient_in_snapshot(
        snapshot,
        patient_id=canonical_patient_id,
        external_case_id=str(ensure_payload.get("external_case_id") or ""),
        source=str(ensure_payload.get("source") or ""),
    )
    patient_record = dict(snapshot_patient or ensured_patient)
    from_room_id = str(patient_record.get("roomId") or patient_record.get("room_id") or explicit_from_room_id).strip()
    already_at_target = decision.to_room_id != "exit" and from_room_id == decision.to_room_id
    already_hidden = decision.to_room_id == "exit" and str(patient_record.get("form") or "") == "hidden"
    if already_at_target or already_hidden:
        result = {
            "ok": True,
            "skipped": True,
            "stage": "move_patient",
            "reason": "ALREADY_SYNCED",
            "ensure": ensure_response,
            "move": None,
            "patient_id": canonical_patient_id,
        }
        _append_adapter_log(config.runtime_root, result)
        return result

    move_payload = {
        "request_id": _stable_request_id(
            patient_id=canonical_patient_id,
            encounter_id=str(ensure_payload.get("external_case_id") or ""),
            event_id=decision.event_id,
            from_room_id=from_room_id,
            to_room_id=decision.to_room_id,
        ),
        "operator_id": config.operator_id,
        "event_id": decision.event_id,
        "patient_id": canonical_patient_id,
        "from_room_id": from_room_id,
        "to_room_id": decision.to_room_id,
        "context": dict(ensure_payload.get("context") or {}),
    }
    move_response = client.move_patient(move_payload)
    result = {
        "ok": bool(move_response.get("accepted", False)),
        "stage": "move_patient",
        "ensure": ensure_response,
        "move": move_response,
        "patient_id": canonical_patient_id,
        "request_id": move_payload["request_id"],
    }
    _append_adapter_log(config.runtime_root, result)
    return result


def _stable_request_id(*, patient_id: str, encounter_id: str, event_id: str, from_room_id: str, to_room_id: str) -> str:
    raw = f"{patient_id}|{encounter_id}|{event_id}|{from_room_id}|{to_room_id}"
    return f"edmas-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _append_adapter_log(runtime_root: Path, payload: Dict[str, Any]) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    log_path = runtime_root / "adapter_events.jsonl"
    record = dict(payload)
    record["logged_at"] = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
