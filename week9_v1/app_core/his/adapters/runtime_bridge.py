from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import shutil
import sqlite3
import uuid

from app_core.his.adapters.contract_adapter import build_event_envelope_placeholder, normalize_ctas_level, normalize_zone
from app_core.his.adapters.memory_adapter import (
    persist_current_summary_to_his,
    persist_handoff_snapshot_to_his,
    persist_memory_item_to_his,
    write_timeline_export_document,
)
from app_core.his.schemas import (
    AuditLogEntry,
    ClinicalAssessmentRecord,
    CurrentSummaryRecord,
    DiagnosisRecord,
    EncounterRecord,
    HandoffSnapshotRecord,
    ImagingRequestRecord,
    ImagingResultRecord,
    LabRequestRecord,
    LabResultRecord,
    OrderRecord,
    PatientRecord,
    TriageRecord,
    VitalSignsRecord,
)
from app_core.his.services.audit_service import append_audit_log, list_audit_logs
from app_core.his.services.encounter_service import (
    get_current_summary,
    get_encounter,
    open_encounter,
    record_clinical_assessment,
    record_diagnosis,
    record_vital_signs,
    update_encounter_state,
)
from app_core.his.services.event_registry_service import list_event_registry_entries
from app_core.his.services.handoff_service import get_handoff_snapshots
from app_core.his.services.imaging_service import create_imaging_request, record_imaging_result
from app_core.his.services.lab_service import create_lab_request, record_lab_result
from app_core.his.services.order_service import create_order
from app_core.his.services.outbox_service import enqueue_outbox_event, list_outbox_events
from app_core.his.services.patient_registry_service import get_patient, register_patient
from app_core.his.services.triage_service import get_triage, record_triage
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage
from app_core.memory.hooks import build_audit_record, build_handoff_snapshot_id, build_memory_event, generate_user_run_id, next_memory_step
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem
from app_core.memory.service import MemoryService, create_memory_service

_RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "runtime_data" / "week9_his_runtime"
_RUNTIME_DB_PATH = _RUNTIME_ROOT / "his" / "his_runtime.sqlite3"
_RUNTIME_MEMORY_ROOT = _RUNTIME_ROOT / "memory"
_RUNTIME_STORAGE: SQLiteDevHisStorage | None = None
_RUNTIME_MEMORY: MemoryService | None = None
_RUNTIME_ARTIFACTS: dict[str, dict[str, Any]] = {}


def _artifact_bucket(encounter_id: str, *, run_id: str | None = None, mode: str = "user") -> dict[str, Any]:
    bucket = _RUNTIME_ARTIFACTS.setdefault(
        encounter_id,
        {
            "run_id": run_id or "",
            "mode": mode,
            "memory_ids": [],
            "event_ids": [],
            "summary_ids": [],
            "snapshot_ids": [],
            "document_ids": [],
            "document_registry_ids": [],
            "orders": [],
            "lab_requests": [],
            "lab_results": [],
            "imaging_requests": [],
            "imaging_results": [],
            "closed": False,
            "doctor_started": False,
        },
    )
    if run_id:
        bucket["run_id"] = run_id
    bucket["mode"] = mode
    return bucket


def get_runtime_storage() -> SQLiteDevHisStorage:
    global _RUNTIME_STORAGE
    if _RUNTIME_STORAGE is None:
        _RUNTIME_STORAGE = SQLiteDevHisStorage(db_path=_RUNTIME_DB_PATH)
        _RUNTIME_STORAGE.bootstrap()
    return _RUNTIME_STORAGE


def get_runtime_memory_service() -> MemoryService:
    global _RUNTIME_MEMORY
    if _RUNTIME_MEMORY is None:
        _RUNTIME_MEMORY = create_memory_service(root=_RUNTIME_MEMORY_ROOT, enabled=True)
    return _RUNTIME_MEMORY


def reset_runtime_bridge_state() -> None:
    global _RUNTIME_STORAGE, _RUNTIME_MEMORY
    _RUNTIME_STORAGE = None
    _RUNTIME_MEMORY = None
    _RUNTIME_ARTIFACTS.clear()
    if _RUNTIME_DB_PATH.exists():
        with sqlite3.connect(_RUNTIME_DB_PATH) as conn:
            tables = [
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if row[0] != "sqlite_sequence"
            ]
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
    if _RUNTIME_MEMORY_ROOT.exists():
        shutil.rmtree(_RUNTIME_MEMORY_ROOT)


def register_runtime_patient(
    *,
    patient_id: str | None,
    display_name: str,
    identifiers: dict[str, Any] | None = None,
) -> PatientRecord:
    storage = get_runtime_storage()
    actual_patient_id = patient_id
    if actual_patient_id and not actual_patient_id.startswith("P-"):
        identifiers = dict(identifiers or {})
        identifiers.setdefault("external_patient_id", actual_patient_id)
        actual_patient_id = None
    patient = PatientRecord(
        patient_id=actual_patient_id or PatientRecord().patient_id,
        full_name=display_name or "Patient 1",
        identifiers=dict(identifiers or {}),
    )
    existing = get_patient(patient.patient_id, storage=storage)
    if existing is not None:
        return existing
    return register_patient(patient, storage=storage)


def _checkpoint_for_event(event_type: str) -> str:
    return {
        "encounter_started": "encounter_started",
        "calling_nurse_called": "encounter_started",
        "vitals_measured": "post_triage",
        "triage_completed": "post_triage",
        "doctor_assessment_started": "doctor_assessment_start",
        "doctor_assessment_checkpoint": "doctor_assessment_checkpoint",
        "test_ordered": "doctor_assessment_checkpoint",
        "test_result_ready": "test_result_ready",
        "handoff_requested": "handoff_requested",
        "handoff_completed": "handoff_completed",
        "disposition_decided": "encounter_closed",
        "encounter_closed": "encounter_closed",
        "next_slot": "next_slot",
    }.get(event_type, "next_slot")


def _append_memory_event(
    *,
    run_id: str,
    mode: str,
    encounter_id: str,
    patient_id: str,
    step: int,
    agent_role: str,
    event_type: str,
    source: str,
    content: str,
    structured_facts: dict[str, Any],
    tags: list[str] | None = None,
) -> MemoryItem:
    storage = get_runtime_storage()
    memory = get_runtime_memory_service()
    item = build_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step,
        agent_role=agent_role,
        event_type=event_type,
        source=source,
        priority="routine",
        content=content,
        structured_facts=structured_facts,
        tags=tags or [],
    )
    memory.append_event(item)
    event_entry = persist_memory_item_to_his(item, storage=storage)
    memory.append_audit(
        build_audit_record(
            run_id=run_id,
            mode=mode,
            encounter_id=encounter_id,
            op_type="memory_upgrade",
            checkpoint=_checkpoint_for_event(event_type),
            source_ids=[item.memory_id],
            details={"event_id": event_entry.event_id, "event_type": event_type},
        )
    )
    append_audit_log(
        AuditLogEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:12]}",
            action=event_type,
            actor=agent_role,
            patient_id=patient_id,
            encounter_id=encounter_id,
            details={"memory_id": item.memory_id, "event_id": event_entry.event_id},
        ),
        storage=storage,
    )
    enqueue_outbox_event(
        event_type=event_type,
        encounter_id=encounter_id,
        payload=build_event_envelope_placeholder(
            event_type=event_type,
            patient_id=patient_id,
            encounter_id=encounter_id,
            source=source,
            payload={"memory_id": item.memory_id, **structured_facts},
            event_id=event_entry.event_id,
        ),
        storage=storage,
    )
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    bucket["memory_ids"].append(item.memory_id)
    bucket["event_ids"].append(event_entry.event_id)
    return item


def _build_summary(
    *,
    run_id: str,
    mode: str,
    encounter_id: str,
    patient_id: str,
    current_state: str,
    current_zone: str,
    acuity: str,
    latest_vitals: dict[str, Any],
    latest_doctor_findings: dict[str, Any] | None = None,
    latest_test_status: dict[str, Any] | None = None,
    pending_tasks: list[dict[str, Any]] | None = None,
    completed_actions: list[dict[str, Any]] | None = None,
    active_risks: list[dict[str, Any]] | None = None,
    source_memory_ids: list[str] | None = None,
) -> CurrentEncounterSummary:
    return CurrentEncounterSummary(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        current_state=current_state,
        current_zone=current_zone,
        acuity=acuity,
        latest_vitals=dict(latest_vitals),
        active_risks=list(active_risks or []),
        pending_tasks=list(pending_tasks or []),
        completed_actions=list(completed_actions or []),
        latest_doctor_findings=dict(latest_doctor_findings or {}),
        latest_test_status=dict(latest_test_status or {}),
        source_memory_ids=list(source_memory_ids or []),
        updated_at_step=len(list(source_memory_ids or [])),
    )


def _persist_summary(summary: CurrentEncounterSummary) -> CurrentSummaryRecord:
    memory = get_runtime_memory_service()
    memory.update_current_summary(summary)
    stored = persist_current_summary_to_his(summary, storage=get_runtime_storage())
    _artifact_bucket(summary.encounter_id, run_id=summary.run_id, mode=summary.mode)["summary_ids"].append(stored.summary_id)
    return stored


def _maybe_seed_stemi_workup(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    mode: str,
    chief_complaint: str,
    symptoms: list[str],
    latest_vitals: dict[str, Any],
    doctor_data: dict[str, Any],
    step: int,
) -> dict[str, Any]:
    merged = f"{chief_complaint} {' '.join(symptoms)}".lower()
    red_flags = doctor_data.get("red_flags", {}) if isinstance(doctor_data, dict) else {}
    chest_pain_like = "chest pain" in merged or "stemi" in merged
    high_risk = bool(red_flags.get("radiating_pain")) or bool(red_flags.get("syncope"))
    unstable = float(latest_vitals.get("spo2", 100)) < 95 or float(latest_vitals.get("sbp", 120)) <= 110
    if not (chest_pain_like and (high_risk or unstable)):
        return {}

    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    if bucket["orders"]:
        return {
            "orders": list(bucket["orders"]),
            "lab_requests": list(bucket["lab_requests"]),
            "lab_results": list(bucket["lab_results"]),
            "imaging_requests": list(bucket["imaging_requests"]),
            "imaging_results": list(bucket["imaging_results"]),
        }

    storage = get_runtime_storage()
    order = create_order(
        OrderRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            order_id=f"ord-{uuid.uuid4().hex[:10]}",
            order_type="stemi_workup",
            payload={"components": ["ecg", "troponin", "portable_xray"]},
        ),
        storage=storage,
    )
    lab_request = create_lab_request(
        LabRequestRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            request_id=f"labreq-{uuid.uuid4().hex[:10]}",
            order_id=order.order_id,
            test_code="troponin",
            payload={"priority": "stat"},
        ),
        storage=storage,
    )
    lab_result = record_lab_result(
        LabResultRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            result_id=f"labres-{uuid.uuid4().hex[:10]}",
            request_id=lab_request.request_id,
            payload={"troponin": "positive", "interpretation": "stemi_concern"},
        ),
        storage=storage,
    )
    imaging_request = create_imaging_request(
        ImagingRequestRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            request_id=f"imgreq-{uuid.uuid4().hex[:10]}",
            order_id=order.order_id,
            modality="portable_xray",
            payload={"reason": "chest pain workup"},
        ),
        storage=storage,
    )
    imaging_result = record_imaging_result(
        ImagingResultRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            result_id=f"imgres-{uuid.uuid4().hex[:10]}",
            request_id=imaging_request.request_id,
            payload={"finding": "no_focal_infiltrate", "status": "completed"},
        ),
        storage=storage,
    )
    bucket["orders"].append(order.to_dict())
    bucket["lab_requests"].append(lab_request.to_dict())
    bucket["lab_results"].append(lab_result.to_dict())
    bucket["imaging_requests"].append(imaging_request.to_dict())
    bucket["imaging_results"].append(imaging_result.to_dict())
    _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step,
        agent_role="doctor",
        event_type="test_ordered",
        source="his_bridge",
        content="STEMI workup orders were placed through HIS services.",
        structured_facts={"order_id": order.order_id, "lab_request_id": lab_request.request_id, "imaging_request_id": imaging_request.request_id},
        tags=["stemi", "orders"],
    )
    _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step + 1,
        agent_role="doctor",
        event_type="test_result_ready",
        source="his_bridge",
        content="Initial STEMI workup results are available.",
        structured_facts={"lab_result_id": lab_result.result_id, "imaging_result_id": imaging_result.result_id},
        tags=["stemi", "results"],
    )
    return {
        "orders": list(bucket["orders"]),
        "lab_requests": list(bucket["lab_requests"]),
        "lab_results": list(bucket["lab_results"]),
        "imaging_requests": list(bucket["imaging_requests"]),
        "imaging_results": list(bucket["imaging_results"]),
    }


def start_formal_encounter(
    *,
    requested_patient_id: str | None,
    display_name: str,
    chief_complaint: str,
    symptoms: list[str],
    vitals: dict[str, Any],
    triage_payload: dict[str, Any],
    arrival_mode: str,
    final_state: str,
    mode: str = "user",
    run_id: str | None = None,
) -> dict[str, Any]:
    storage = get_runtime_storage()
    run_id = run_id or generate_user_run_id()
    patient = register_runtime_patient(patient_id=requested_patient_id, display_name=display_name, identifiers={"mode": mode})
    encounter = open_encounter(
        EncounterRecord(
            patient_id=patient.patient_id,
            arrival_mode=arrival_mode,
            metadata={"chief_complaint": chief_complaint, "symptoms": list(symptoms), "mode": mode, "run_id": run_id},
        ),
        storage=storage,
    )
    ctas_level = normalize_ctas_level(triage_payload.get("ctas_compat") or triage_payload.get("ctas_level") or triage_payload.get("acuity_ad") or "L3")
    zone = normalize_zone(triage_payload.get("zone"), ctas_level)
    triage = record_triage(
        TriageRecord(
            encounter_id=encounter.encounter_id,
            patient_id=patient.patient_id,
            triage_id=f"triage-{uuid.uuid4().hex[:10]}",
            ctas_level=ctas_level,
            zone=zone,
            summary=chief_complaint,
            structured_data=dict(triage_payload),
        ),
        storage=storage,
    )
    vitals_record = record_vital_signs(
        VitalSignsRecord(
            encounter_id=encounter.encounter_id,
            patient_id=patient.patient_id,
            vital_id=f"vitals-{uuid.uuid4().hex[:10]}",
            readings=dict(vitals),
        ),
        storage=storage,
    )
    updated_encounter = update_encounter_state(
        encounter.encounter_id,
        status=final_state or "TRIAGED",
        current_zone=zone,
        ctas_level=ctas_level,
        storage=storage,
    )
    bucket = _artifact_bucket(encounter.encounter_id, run_id=run_id, mode=mode)
    step = next_memory_step(None)
    started = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        step=step,
        agent_role="system",
        event_type="encounter_started",
        source="api_v1.start_encounter",
        content=f"Encounter opened for {chief_complaint}.",
        structured_facts={"arrival_mode": arrival_mode, "final_state": final_state},
        tags=["encounter"],
    )
    measured = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        step=next_memory_step(step),
        agent_role="calling_nurse",
        event_type="vitals_measured",
        source="api_v1.user_mode_chat_turn",
        content="Calling nurse recorded a vital signs checkpoint.",
        structured_facts={"vitals": dict(vitals)},
        tags=["vitals"],
    )
    triaged = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        step=next_memory_step(measured.step),
        agent_role="triage_nurse",
        event_type="triage_completed",
        source="api_v1.start_encounter",
        content=f"Triage normalized to {ctas_level} / {zone}.",
        structured_facts={"triage": dict(triage_payload), "ctas_level": ctas_level, "zone": zone},
        tags=["triage"],
    )
    summary = _build_summary(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        current_state=final_state or "TRIAGED",
        current_zone=zone,
        acuity=ctas_level,
        latest_vitals=dict(vitals),
        pending_tasks=[{"task": "doctor_assessment"}],
        source_memory_ids=[started.memory_id, measured.memory_id, triaged.memory_id],
    )
    stored_summary = _persist_summary(summary)
    bucket["last_summary_state"] = stored_summary.current_state
    return {
        "patient": patient,
        "encounter": updated_encounter,
        "triage": triage,
        "vitals": vitals_record,
        "summary": stored_summary,
        "run_id": run_id,
    }


def record_doctor_stage_started(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    shared_memory: dict[str, Any],
    triage_payload: dict[str, Any],
    mode: str = "user",
) -> MemoryItem | None:
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    if bucket["doctor_started"]:
        return None
    ctas_level = normalize_ctas_level(triage_payload.get("ctas_compat") or triage_payload.get("ctas_level") or triage_payload.get("acuity_ad") or "L3")
    zone = normalize_zone(triage_payload.get("zone"), ctas_level)
    item = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=next_memory_step(len(bucket["memory_ids"]) - 1),
        agent_role="doctor",
        event_type="doctor_assessment_started",
        source="api_v1.user_mode_chat_turn",
        content="Doctor assessment phase started.",
        structured_facts={"chief_complaint": shared_memory.get("chief_complaint", ""), "ctas_level": ctas_level, "zone": zone},
        tags=["doctor"],
    )
    summary = _build_summary(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        current_state="doctor_assessment",
        current_zone=zone,
        acuity=ctas_level,
        latest_vitals=dict(shared_memory.get("vitals", {})),
        pending_tasks=[{"task": "collect_doctor_history"}],
        completed_actions=[{"action": "triage_completed"}],
        source_memory_ids=list(bucket["memory_ids"]),
    )
    _persist_summary(summary)
    bucket["doctor_started"] = True
    return item


def record_doctor_checkpoint(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    shared_memory: dict[str, Any],
    doctor_data: dict[str, Any],
    triage_payload: dict[str, Any],
    disposition_target: str | None = None,
    mode: str = "user",
) -> dict[str, Any]:
    storage = get_runtime_storage()
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    ctas_level = normalize_ctas_level(triage_payload.get("ctas_compat") or triage_payload.get("ctas_level") or triage_payload.get("acuity_ad") or "L3")
    zone = normalize_zone(triage_payload.get("zone"), ctas_level)
    findings = {
        "chief_complaint": shared_memory.get("chief_complaint", ""),
        "symptoms": list(shared_memory.get("symptoms", []) or []),
        "latest_vitals": dict(shared_memory.get("vitals", {}) or {}),
        "doctor_data": dict(doctor_data),
        "triage": dict(triage_payload),
        "disposition_target": disposition_target,
    }
    assessment = record_clinical_assessment(
        ClinicalAssessmentRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            assessment_id=f"assess-{uuid.uuid4().hex[:10]}",
            author_role="doctor",
            findings=findings,
        ),
        storage=storage,
    )
    step = next_memory_step(len(bucket["memory_ids"]) - 1)
    checkpoint_item = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step,
        agent_role="doctor",
        event_type="doctor_assessment_checkpoint",
        source="api_v1.user_mode_chat_turn",
        content="Doctor checkpoint persisted to HIS.",
        structured_facts={"assessment_id": assessment.assessment_id, "disposition_target": disposition_target or ""},
        tags=["doctor"],
    )
    diagnosis = record_diagnosis(
        DiagnosisRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            diagnosis_id=f"diag-{uuid.uuid4().hex[:10]}",
            label="STEMI concern" if "chest pain" in str(shared_memory.get("chief_complaint", "")).lower() else "ED working diagnosis",
            details={"disposition_target": disposition_target or "continue_assessment"},
        ),
        storage=storage,
    )
    stemi_workup = _maybe_seed_stemi_workup(
        encounter_id=encounter_id,
        patient_id=patient_id,
        run_id=run_id,
        mode=mode,
        chief_complaint=str(shared_memory.get("chief_complaint", "")),
        symptoms=list(shared_memory.get("symptoms", []) or []),
        latest_vitals=dict(shared_memory.get("vitals", {}) or {}),
        doctor_data=doctor_data,
        step=next_memory_step(step),
    )
    if disposition_target:
        _append_memory_event(
            run_id=run_id,
            mode=mode,
            encounter_id=encounter_id,
            patient_id=patient_id,
            step=next_memory_step(next_memory_step(step)),
            agent_role="doctor",
            event_type="disposition_decided",
            source="api_v1.user_mode_chat_turn",
            content=f"Doctor disposition decided: {disposition_target}.",
            structured_facts={"disposition_target": disposition_target},
            tags=["disposition"],
        )
    latest_test_status = {"stemi_workup": stemi_workup} if stemi_workup else {}
    summary = _build_summary(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        current_state="awaiting_handoff" if disposition_target else "doctor_assessment",
        current_zone=zone,
        acuity=ctas_level,
        latest_vitals=dict(shared_memory.get("vitals", {}) or {}),
        latest_doctor_findings=findings,
        latest_test_status=latest_test_status,
        pending_tasks=[] if disposition_target else [{"task": "continue_doctor_assessment"}],
        completed_actions=[{"action": "doctor_assessment_checkpoint", "assessment_id": assessment.assessment_id}],
        active_risks=[{"risk": key} for key, value in dict(doctor_data.get("red_flags", {})).items() if value is True],
        source_memory_ids=list(bucket["memory_ids"]) + [checkpoint_item.memory_id],
    )
    stored_summary = _persist_summary(summary)
    return {
        "assessment": assessment,
        "diagnosis": diagnosis,
        "summary": stored_summary,
        "stemi_workup": stemi_workup,
    }


def sync_handoff_request(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    target_system: str,
    reason: str,
    shared_memory: dict[str, Any],
    mode: str = "user",
) -> dict[str, Any]:
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    step = next_memory_step(len(bucket["memory_ids"]) - 1)
    event = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step,
        agent_role="doctor",
        event_type="handoff_requested",
        source="api_v1.request_handoff",
        content=f"Handoff requested to {target_system}.",
        structured_facts={"target_system": target_system, "reason": reason},
        tags=["handoff"],
    )
    snapshot = HandoffMemorySnapshot(
        snapshot_id=build_handoff_snapshot_id(run_id, encounter_id, "requested"),
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        from_role="doctor",
        to_role="bed_nurse",
        handoff_stage="requested",
        patient_brief=str(shared_memory.get("chief_complaint", "")).strip() or reason,
        current_state={
            "phase": "handoff_requested",
            "target_system": target_system,
            "vitals": dict(shared_memory.get("vitals", {}) or {}),
            "triage": dict(shared_memory.get("triage", {}) or {}),
        },
        completed_actions=[{"action": "doctor_assessment"}],
        pending_tasks=[{"task": "bed_assignment", "target_system": target_system}],
        active_risks=[{"risk": "pending_transfer"}],
        next_actions=[{"action": "complete_handoff"}],
        source_memory_ids=list(bucket["memory_ids"]) + [event.memory_id],
        created_at_step=step,
    )
    get_runtime_memory_service().write_handoff_snapshot(snapshot)
    stored_snapshot, stored_document, stored_registry = persist_handoff_snapshot_to_his(snapshot, storage=get_runtime_storage())
    bucket["snapshot_ids"].append(stored_snapshot.snapshot_id)
    bucket["document_ids"].append(stored_document.document_id)
    bucket["document_registry_ids"].append(stored_registry.registry_id)
    return {
        "snapshot": stored_snapshot,
        "document": stored_document,
        "registry": stored_registry,
    }


def close_formal_encounter(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    final_state: str,
    note: str,
    mode: str = "user",
) -> CurrentSummaryRecord:
    storage = get_runtime_storage()
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    if not bucket["closed"]:
        _append_memory_event(
            run_id=run_id,
            mode=mode,
            encounter_id=encounter_id,
            patient_id=patient_id,
            step=next_memory_step(len(bucket["memory_ids"]) - 1),
            agent_role="system",
            event_type="encounter_closed",
            source="api_v1.complete_handoff",
            content=note,
            structured_facts={"final_state": final_state},
            tags=["close"],
        )
        current = get_encounter(encounter_id, storage=storage)
        if current is not None:
            storage.update_encounter(replace(current, status="CLOSED"))
        bucket["closed"] = True
    triage = get_triage(encounter_id, storage=storage)
    summary = _build_summary(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        current_state=final_state.lower(),
        current_zone=triage.zone if triage is not None else "yellow",
        acuity=triage.ctas_level if triage is not None else "L3",
        latest_vitals={},
        completed_actions=[{"action": "encounter_closed", "final_state": final_state}],
        source_memory_ids=list(bucket["memory_ids"]),
    )
    return _persist_summary(summary)


def sync_handoff_completion(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    receiver_system: str,
    receiver_bed: str | None,
    mode: str = "user",
) -> dict[str, Any]:
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode=mode)
    step = next_memory_step(len(bucket["memory_ids"]) - 1)
    event = _append_memory_event(
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step,
        agent_role="bed_nurse",
        event_type="handoff_completed",
        source="api_v1.complete_handoff",
        content=f"Handoff completed to {receiver_system}.",
        structured_facts={"receiver_system": receiver_system, "receiver_bed": receiver_bed or ""},
        tags=["handoff"],
    )
    snapshot = HandoffMemorySnapshot(
        snapshot_id=build_handoff_snapshot_id(run_id, encounter_id, "completed"),
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        from_role="bed_nurse",
        to_role=receiver_system.lower(),
        handoff_stage="completed",
        patient_brief=f"Transferred to {receiver_system}",
        current_state={"receiver_system": receiver_system, "receiver_bed": receiver_bed or ""},
        completed_actions=[{"action": "handoff_completed", "receiver_system": receiver_system}],
        pending_tasks=[],
        active_risks=[],
        next_actions=[{"action": "encounter_close"}],
        source_memory_ids=list(bucket["memory_ids"]) + [event.memory_id],
        created_at_step=step,
    )
    get_runtime_memory_service().write_handoff_snapshot(snapshot)
    stored_snapshot, stored_document, stored_registry = persist_handoff_snapshot_to_his(snapshot, storage=get_runtime_storage())
    bucket["snapshot_ids"].append(stored_snapshot.snapshot_id)
    bucket["document_ids"].append(stored_document.document_id)
    bucket["document_registry_ids"].append(stored_registry.registry_id)
    summary = close_formal_encounter(
        encounter_id=encounter_id,
        patient_id=patient_id,
        run_id=run_id,
        final_state=receiver_system,
        note=f"Encounter formally closed after {receiver_system} handoff.",
        mode=mode,
    )
    return {
        "snapshot": stored_snapshot,
        "document": stored_document,
        "registry": stored_registry,
        "summary": summary,
    }


def get_summary_view(encounter_id: str) -> dict[str, Any]:
    storage = get_runtime_storage()
    encounter = get_encounter(encounter_id, storage=storage)
    if encounter is None:
        raise KeyError(f"Encounter not found: {encounter_id}")
    patient = get_patient(encounter.patient_id, storage=storage)
    triage = get_triage(encounter_id, storage=storage)
    summary = get_current_summary(encounter_id, storage=storage)
    handoffs = get_handoff_snapshots(encounter_id, storage=storage)
    vitals = storage.list_vital_signs(encounter_id)
    return {
        "patient": patient.to_dict() if patient is not None else None,
        "encounter": encounter.to_dict(),
        "triage": triage.to_dict() if triage is not None else None,
        "summary": summary.to_dict() if summary is not None else None,
        "latest_vitals": vitals[-1].to_dict() if vitals else None,
        "handoff_count": len(handoffs),
    }


def _empty_replay_payload() -> dict[str, Any]:
    return {
        "events": [],
        "summaries": [],
        "snapshots": [],
        "audits": [],
    }


def _load_replay_payload(*, run_id: str, mode: str, encounter_id: str) -> dict[str, Any]:
    if not run_id:
        return _empty_replay_payload()
    return get_runtime_memory_service().export_replay(run_id=run_id, mode=mode, encounter_id=encounter_id)


def _append_unique(bucket_items: list[str], value: str) -> None:
    if value and value not in bucket_items:
        bucket_items.append(value)


def _derive_auto_contract_alignment(
    *,
    raw_patient_id: str,
    raw_encounter_id: str,
    replay: dict[str, Any],
    scenario_metadata: dict[str, Any] | None,
) -> dict[str, str]:
    formal_patient_id = str((scenario_metadata or {}).get("formal_patient_id", "")).strip()
    if not formal_patient_id:
        formal_patient_id = f"P-{uuid.uuid5(uuid.NAMESPACE_URL, raw_patient_id).hex[:8]}"

    formal_encounter_id = str((scenario_metadata or {}).get("formal_encounter_id", "")).strip()
    if not formal_encounter_id:
        raw_ts = ""
        if replay["events"]:
            raw_ts = str(replay["events"][0].get("wall_time") or replay["events"][0].get("created_at") or "").strip()
        try:
            parsed = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")) if raw_ts else datetime.now(timezone.utc)
        except ValueError:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        formal_encounter_id = f"E-{parsed.astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid5(uuid.NAMESPACE_URL, raw_encounter_id).hex[:4]}"

    return {
        "raw_patient_id": raw_patient_id,
        "raw_encounter_id": raw_encounter_id,
        "formal_patient_id": formal_patient_id,
        "formal_encounter_id": formal_encounter_id,
    }


def _normalize_auto_replay_for_his(replay: dict[str, Any], alignment: dict[str, str]) -> dict[str, Any]:
    def _rewrite(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["patient_id"] = alignment["formal_patient_id"]
        normalized["encounter_id"] = alignment["formal_encounter_id"]
        return normalized

    return {
        "events": [_rewrite(payload) for payload in replay["events"]],
        "summaries": [_rewrite(payload) for payload in replay["summaries"]],
        "snapshots": [_rewrite(payload) for payload in replay["snapshots"]],
        "audits": list(replay["audits"]),
    }


def _ensure_auto_runtime_records(
    *,
    encounter_id: str,
    run_id: str,
    replay: dict[str, Any],
    patient_id: str | None,
    patient_display_name: str | None,
    scenario_metadata: dict[str, Any] | None,
) -> tuple[PatientRecord, EncounterRecord]:
    storage = get_runtime_storage()
    latest_summary = replay["summaries"][-1] if replay["summaries"] else {}
    first_event = replay["events"][0] if replay["events"] else {}
    resolved_patient_id = (
        patient_id
        or str(first_event.get("patient_id", "")).strip()
        or str(latest_summary.get("patient_id", "")).strip()
        or f"P-{encounter_id}"
    )
    resolved_name = (
        patient_display_name
        or str((scenario_metadata or {}).get("patient_display_name", "")).strip()
        or str((first_event.get("structured_facts", {}) or {}).get("patient_name", "")).strip()
        or str((latest_summary.get("latest_doctor_findings", {}) or {}).get("patient_name", "")).strip()
        or resolved_patient_id.replace("_", " ")
    )
    patient = get_patient(resolved_patient_id, storage=storage)
    if patient is None:
        patient = register_patient(
            PatientRecord(
                patient_id=resolved_patient_id,
                full_name=resolved_name,
                identifiers={
                    "auto_run_id": run_id,
                    "source": "auto_timeline_export",
                },
            ),
            storage=storage,
        )

    encounter = get_encounter(encounter_id, storage=storage)
    if encounter is None:
        ctas_level = normalize_ctas_level(
            str(
                latest_summary.get("acuity")
                or (latest_summary.get("current_state") or {}).get("ctas_level")
                or (scenario_metadata or {}).get("ctas_level")
                or "L3"
            )
        )
        current_zone = normalize_zone(
            latest_summary.get("current_zone") or (scenario_metadata or {}).get("current_zone"),
            ctas_level,
        )
        encounter = open_encounter(
            EncounterRecord(
                encounter_id=encounter_id,
                patient_id=patient.patient_id,
                status="OPEN",
                arrival_mode="simulation",
                current_zone=current_zone,
                ctas_level=ctas_level,
                metadata={
                    "mode": "auto",
                    "scenario_metadata": dict(scenario_metadata or {}),
                    "source": "auto_timeline_export",
                },
            ),
            storage=storage,
        )
    return patient, encounter


def _hydrate_auto_replay_into_his(*, encounter_id: str, run_id: str, replay: dict[str, Any]) -> None:
    storage = get_runtime_storage()
    bucket = _artifact_bucket(encounter_id, run_id=run_id, mode="auto")

    existing_event_ids = {item.event_id for item in list_event_registry_entries(encounter_id, storage=storage)}
    for event_payload in replay["events"]:
        item = MemoryItem.from_dict(event_payload)
        entry_id = f"evt-{item.memory_id}"
        if entry_id not in existing_event_ids:
            persist_memory_item_to_his(item, storage=storage)
            existing_event_ids.add(entry_id)
        _append_unique(bucket["memory_ids"], item.memory_id)
        _append_unique(bucket["event_ids"], entry_id)

    if replay["summaries"] and get_current_summary(encounter_id, storage=storage) is None:
        summary = CurrentEncounterSummary.from_dict(replay["summaries"][-1])
        stored_summary = persist_current_summary_to_his(summary, storage=storage)
        _append_unique(bucket["summary_ids"], stored_summary.summary_id)
    elif replay["summaries"]:
        stored_summary_id = str(replay["summaries"][-1].get("summary_id", f"sum-{encounter_id}"))
        _append_unique(bucket["summary_ids"], stored_summary_id)

    existing_snapshot_ids = {item.snapshot_id for item in get_handoff_snapshots(encounter_id, storage=storage)}
    for snapshot_payload in replay["snapshots"]:
        snapshot = HandoffMemorySnapshot.from_dict(snapshot_payload)
        if snapshot.snapshot_id not in existing_snapshot_ids:
            stored_snapshot, stored_document, stored_registry = persist_handoff_snapshot_to_his(snapshot, storage=storage)
            existing_snapshot_ids.add(snapshot.snapshot_id)
            _append_unique(bucket["snapshot_ids"], stored_snapshot.snapshot_id)
            _append_unique(bucket["document_ids"], stored_document.document_id)
            _append_unique(bucket["document_registry_ids"], stored_registry.registry_id)
        else:
            _append_unique(bucket["snapshot_ids"], snapshot.snapshot_id)


def _record_timeline_export(
    *,
    encounter_id: str,
    patient_id: str,
    run_id: str,
    mode: str,
    source_ids: list[str],
    bundle_sections: list[str],
    storage: SQLiteDevHisStorage,
) -> AuditLogEntry:
    get_runtime_memory_service().append_audit(
        build_audit_record(
            run_id=run_id or f"{mode}_export",
            mode=mode,
            encounter_id=encounter_id,
            op_type="timeline_export",
            checkpoint="replay_export",
            source_ids=source_ids,
            details={"bundle_sections": bundle_sections},
        )
    )
    return append_audit_log(
        AuditLogEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:12]}",
            action="timeline_export",
            actor=f"{mode}_timeline_exporter",
            patient_id=patient_id,
            encounter_id=encounter_id,
            details={
                "bundle_sections": bundle_sections,
                "source_memory_ids": source_ids,
            },
        ),
        storage=storage,
    )


def _build_timeline_bundle(
    *,
    encounter_id: str,
    run_id: str,
    mode: str,
    scenario_metadata: dict[str, Any] | None = None,
    replay_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], EncounterRecord, PatientRecord | None, dict[str, Any], SQLiteDevHisStorage]:
    storage = get_runtime_storage()
    encounter = get_encounter(encounter_id, storage=storage)
    if encounter is None:
        raise KeyError(f"Encounter not found: {encounter_id}")
    patient = get_patient(encounter.patient_id, storage=storage)
    triage = get_triage(encounter_id, storage=storage)
    summary = get_current_summary(encounter_id, storage=storage)
    bucket = _artifact_bucket(encounter_id)
    replay = replay_override if replay_override is not None else _load_replay_payload(run_id=run_id, mode=mode, encounter_id=encounter_id)
    bundle = {
        "patient": patient.to_dict() if patient is not None else None,
        "encounter": encounter.to_dict(),
        "triage": triage.to_dict() if triage is not None else None,
        "summary": summary.to_dict() if summary is not None else None,
        "vital_signs": [item.to_dict() for item in storage.list_vital_signs(encounter_id)],
        "clinical_assessments": [item.to_dict() for item in storage.list_clinical_assessments(encounter_id)],
        "diagnoses": [item.to_dict() for item in storage.list_diagnoses(encounter_id)],
        "handoff_snapshots": [item.to_dict() for item in get_handoff_snapshots(encounter_id, storage=storage)],
        "clinical_documents": [item.to_dict() for item in storage.list_documents(encounter_id)],
        "event_registry": [item.to_dict() for item in list_event_registry_entries(encounter_id, storage=storage)],
        "audit_logs": [item.to_dict() for item in list_audit_logs(encounter_id, storage=storage)],
        "outbox_events": [item.to_dict() for item in list_outbox_events(encounter_id, storage=storage)],
        "memory_replay": replay,
        "stemi_workup": {
            "orders": list(bucket["orders"]),
            "lab_requests": list(bucket["lab_requests"]),
            "lab_results": list(bucket["lab_results"]),
            "imaging_requests": list(bucket["imaging_requests"]),
            "imaging_results": list(bucket["imaging_results"]),
        },
    }
    if scenario_metadata:
        bundle["scenario_metadata"] = dict(scenario_metadata)
    return bundle, encounter, patient, bucket, storage


def export_timeline_bundle(encounter_id: str) -> dict[str, Any]:
    bucket = _artifact_bucket(encounter_id)
    run_id = str(bucket.get("run_id", "")).strip()
    mode = str(bucket.get("mode", "user")).strip() or "user"
    bundle, encounter, patient, bucket, storage = _build_timeline_bundle(
        encounter_id=encounter_id,
        run_id=run_id,
        mode=mode,
    )
    audit = _record_timeline_export(
        encounter_id=encounter_id,
        patient_id=encounter.patient_id,
        run_id=run_id,
        mode=mode,
        source_ids=list(dict.fromkeys(bucket["memory_ids"])),
        bundle_sections=sorted(bundle.keys()),
        storage=storage,
    )
    document, registry = write_timeline_export_document(
        encounter_id=encounter_id,
        patient_id=encounter.patient_id,
        bundle=bundle,
        storage=storage,
    )
    bucket["document_ids"].append(document.document_id)
    bucket["document_registry_ids"].append(registry.registry_id)
    return {
        "bundle": bundle,
        "document": document.to_dict(),
        "registry": registry.to_dict(),
        "audit": audit.to_dict(),
    }


def export_auto_timeline_bundle(
    *,
    encounter_id: str,
    run_id: str,
    patient_id: str | None = None,
    patient_display_name: str | None = None,
    scenario_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    replay = _load_replay_payload(run_id=run_id, mode="auto", encounter_id=encounter_id)
    if not any(replay.values()):
        raise KeyError(f"Replay not found for auto encounter: {encounter_id}")
    raw_patient_id = (
        patient_id
        or str((replay["events"][0] if replay["events"] else {}).get("patient_id", "")).strip()
        or str((replay["summaries"][-1] if replay["summaries"] else {}).get("patient_id", "")).strip()
        or "Patient_auto"
    )
    alignment = _derive_auto_contract_alignment(
        raw_patient_id=raw_patient_id,
        raw_encounter_id=encounter_id,
        replay=replay,
        scenario_metadata=scenario_metadata,
    )
    normalized_replay = _normalize_auto_replay_for_his(replay, alignment)
    patient, encounter = _ensure_auto_runtime_records(
        encounter_id=alignment["formal_encounter_id"],
        run_id=run_id,
        replay=normalized_replay,
        patient_id=alignment["formal_patient_id"],
        patient_display_name=patient_display_name,
        scenario_metadata={
            **dict(scenario_metadata or {}),
            **alignment,
        },
    )
    _artifact_bucket(alignment["formal_encounter_id"], run_id=run_id, mode="auto")
    _hydrate_auto_replay_into_his(
        encounter_id=alignment["formal_encounter_id"],
        run_id=run_id,
        replay=normalized_replay,
    )
    bundle, encounter, patient, bucket, storage = _build_timeline_bundle(
        encounter_id=alignment["formal_encounter_id"],
        run_id=run_id,
        mode="auto",
        scenario_metadata={
            **dict(scenario_metadata or {}),
            **alignment,
        },
        replay_override=replay,
    )
    bundle["contract_alignment"] = alignment
    audit = _record_timeline_export(
        encounter_id=alignment["formal_encounter_id"],
        patient_id=patient.patient_id if patient is not None else encounter.patient_id,
        run_id=run_id,
        mode="auto",
        source_ids=list(dict.fromkeys(bucket["memory_ids"])),
        bundle_sections=sorted(bundle.keys()),
        storage=storage,
    )
    document, registry = write_timeline_export_document(
        encounter_id=alignment["formal_encounter_id"],
        patient_id=patient.patient_id if patient is not None else encounter.patient_id,
        bundle=bundle,
        storage=storage,
    )
    _append_unique(bucket["document_ids"], document.document_id)
    _append_unique(bucket["document_registry_ids"], registry.registry_id)
    return {
        "bundle": bundle,
        "document": document.to_dict(),
        "registry": registry.to_dict(),
        "audit": audit.to_dict(),
    }
