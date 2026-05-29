from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os
import re
import uuid

from app_core.app.llm_adapter import generate_clinical_reply
from app_core.app.mode_user import start as run_user_mode
from app_core.app.planning.doctor_planner import build_doctor_plan
from app_core.app.planning.plan_validator import validate_plan
from app_core.app.rag.evidence_builder import build_evidence_package
from app_core.app.rag.protocol_retriever import retrieve_protocols
from app_core.app.schema import PayloadError, validate_encounter_start_payload
from app_core.his.adapters.contract_adapter import build_event_envelope, derive_zone_from_ctas
from app_core.his.config import generate_encounter_id as generate_his_encounter_id
from app_core.his.config import generate_patient_id as generate_his_patient_id
from app_core.his.schemas import (
    AuditLogEntry,
    ClinicalAssessmentRecord,
    CurrentSummaryRecord,
    DiagnosisRecord,
    EncounterRecord,
    EventRegistryEntry,
    HandoffSnapshotRecord,
    PatientRecord,
    TriageRecord,
    VitalSignsRecord,
)
from app_core.his.services.audit_service import append_audit_log
from app_core.his.services.encounter_service import (
    open_encounter as his_open_encounter,
    record_clinical_assessment,
    record_diagnosis,
    record_vital_signs,
    update_encounter_state,
    write_current_summary,
)
from app_core.his.services.event_registry_service import append_event_registry_entry
from app_core.his.services.handoff_service import write_handoff_snapshot
from app_core.his.services.outbox_service import enqueue_outbox_event
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.services.triage_service import record_triage
from app_core.his.storage import create_his_storage
from app_core.his.storage.base import HisStorage
from app_core.doctor_rag.bridge import run_bridge
from app_core.clinical_kb.registry import registry_map


ALLOWED_RECEIVER_SYSTEMS = {"OUTPATIENT", "ICU", "WARD"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "environment" / "frontend_server"
TEMP_ROOT = Path(os.environ.get("EDSIM_TEMP_DIR", str(FRONTEND_ROOT / "temp_storage")))
STORAGE_ROOT = FRONTEND_ROOT / "storage"


@dataclass
class ApiError(Exception):
    message: str
    status_code: int = 400
    error_code: str = "INVALID_REQUEST"
    field_errors: Optional[List[Dict[str, str]]] = None

    def __str__(self) -> str:
        return self.message


_ENCOUNTERS: Dict[str, Dict[str, Any]] = {}
_HANDOFF_TICKETS: Dict[str, Dict[str, Any]] = {}
_USER_MODE_SESSION: Optional[Dict[str, Any]] = None
_HIS_STORAGE: Optional[HisStorage] = None

_SMALLTALK_PATTERNS = {
    "hi",
    "hello",
    "hey",
    "ok",
    "okay",
    "yes",
    "no",
    "你好",
    "在吗",
    "好的",
}

_SPELLING_FIXES = {
    "lowfeaver": "low fever",
    "feaver": "fever",
    "pheomonia": "pneumonia",
    "pheomoniabefore": "pneumonia before",
    "ihave": "i have",
    "ican'tmeasur": "i can't measure",
    "icantmeasure": "i can't measure",
    "ihanven'thadtheseinformation": "i have not had this information",
}

_SYMPTOM_KEYWORDS = {
    "chest pain": ["chest pain", "chest hurts", "胸痛", "胸口疼", "胸口很疼", "胸闷"],
    "shortness of breath": ["shortness of breath", "sob", "dyspnea", "呼吸困难", "喘不上气"],
    "fever": ["fever", "发烧", "低烧", "low fever"],
    "cough": ["cough", "咳嗽"],
    "nausea": ["nausea", "恶心"],
    "vomiting": ["vomit", "vomiting", "呕吐"],
    "dizziness": ["dizziness", "dizzy", "头晕"],
    "back pain": ["back pain", "low back pain", "腰痛", "背痛", "腰背痛", "下背痛"],
    "abdominal pain": ["abdominal pain", "belly pain", "腹痛", "肚子疼"],
    "labor": ["labor", "delivery", "giving birth", "分娩", "生小孩", "要生了", "宫缩", "羊水破了", "破水"],
    "allergic reaction": ["allergic reaction", "anaphylaxis", "hives", "throat tight", "过敏反应", "荨麻疹", "喉咙紧"],
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_path(*parts: str) -> Path:
    return STORAGE_ROOT.joinpath(*parts)


def _temp_path(*parts: str) -> Path:
    return TEMP_ROOT.joinpath(*parts)


def _current_sim_code() -> str:
    try:
        payload = json.loads(_temp_path("curr_sim_code.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    return str(payload.get("sim_code") or "").strip()


def _load_auto_runtime_snapshot() -> Dict[str, Any]:
    sim_code = _current_sim_code()
    if not sim_code:
        return {"available": False}

    status_path = _storage_path(sim_code, "sim_status.json")
    meta_path = _storage_path(sim_code, "reverie", "meta.json")
    try:
        status_payload = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        meta_payload = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {"available": False, "sim_code": sim_code}

    queue_entries: List[Dict[str, Any]] = []
    for raw_entry in meta_payload.get("patients_waiting_for_doctor", []) or []:
        if not isinstance(raw_entry, list) or len(raw_entry) < 2:
            continue
        try:
            priority = float(raw_entry[0])
        except (TypeError, ValueError):
            continue
        queue_entries.append({"priority": priority, "name": str(raw_entry[1])})

    return {
        "available": True,
        "sim_code": sim_code,
        "doctor_global_queue": int(((status_payload.get("queues") or {}).get("doctor_global")) or len(queue_entries)),
        "triage_queue": int(((status_payload.get("queues") or {}).get("triage")) or 0),
        "priority_factor": float(meta_payload.get("priority_factor") or 2),
        "doctor_queue_entries": queue_entries,
    }


def _write_reverie_command(command: str, args: Dict[str, Any]) -> str:
    cmd_dir = _temp_path("commands")
    cmd_dir.mkdir(parents=True, exist_ok=True)
    cmd_id = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    payload = {
        "id": cmd_id,
        "command": command,
        "args": dict(args),
        "created_at": _utc_now_iso(),
    }
    (cmd_dir / f"cmd_{cmd_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return cmd_id


def _auto_persona_name(session: Dict[str, Any]) -> str:
    existing = str(session.get("auto_persona_name") or "").strip()
    if existing:
        return existing
    patient_id = str(session.get("patient_id") or "Patient").strip()
    persona_name = f"User {patient_id}"
    session["auto_persona_name"] = persona_name
    return persona_name


def _derive_internal_injuries_zone_from_ctas(ctas: int) -> str:
    """
    Map contract CTAS (1-5) to the EDSim internal room vocabulary.

    Note: Contract `zone` is a 3-color derived field (red/yellow/green). Internal room names
    (trauma/major/minor) should not leak into contract-facing fields.
    """
    level = int(ctas or 3)
    if level <= 1:
        return "trauma room"
    if level == 2:
        return "major injuries zone"
    return "minor injuries zone"


def _sync_user_patient_to_auto(session: Dict[str, Any], *, enqueue_doctor: bool, user_phase: str) -> None:
    auto_snapshot = _load_auto_runtime_snapshot()
    if not auto_snapshot.get("available"):
        return
    triage = dict(session.get("shared_memory", {}).get("triage", {}) or {})
    chief_complaint = str(session.get("shared_memory", {}).get("chief_complaint", "")).strip()
    ctas = int(triage.get("ctas_compat") or triage.get("level_1_4") or 3)
    priority_factor = float(auto_snapshot.get("priority_factor") or 2)
    args = {
        "persona_name": _auto_persona_name(session),
        "user_patient_id": session.get("patient_id"),
        "user_encounter_id": session.get("encounter_id"),
        "chief_complaint": chief_complaint,
        "injuries_zone": _derive_internal_injuries_zone_from_ctas(ctas),
        "ctas": ctas,
        "user_phase": user_phase,
        "enqueue_doctor": enqueue_doctor,
        "doctor_priority": float(ctas * priority_factor),
    }
    try:
        _write_reverie_command("inject_user_patient", args)
    except OSError:
        return


def _parse_iso(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _get_his_storage() -> HisStorage:
    global _HIS_STORAGE
    if _HIS_STORAGE is None:
        _HIS_STORAGE = create_his_storage()
    return _HIS_STORAGE


def _set_his_storage_for_tests(storage: Optional[HisStorage]) -> None:
    global _HIS_STORAGE
    _HIS_STORAGE = storage


def _ensure_his_identifiers(encounter: Dict[str, Any]) -> tuple[str, str]:
    his_patient_id = str(encounter.get("his_patient_id") or "").strip()
    his_encounter_id = str(encounter.get("his_encounter_id") or "").strip()
    if not his_patient_id:
        his_patient_id = generate_his_patient_id()
        encounter["his_patient_id"] = his_patient_id
    if not his_encounter_id:
        his_encounter_id = generate_his_encounter_id()
        encounter["his_encounter_id"] = his_encounter_id
    return his_patient_id, his_encounter_id


def _append_his_event(
    *,
    his_patient_id: str,
    his_encounter_id: str,
    event_type: str,
    source: str,
    payload: Dict[str, Any],
    storage: HisStorage,
) -> EventRegistryEntry:
    envelope = build_event_envelope(
        event_type=event_type,
        patient_id=his_patient_id,
        encounter_id=his_encounter_id,
        source=source,
        payload=payload,
    )
    entry = EventRegistryEntry(
        event_id=str(envelope["event_id"]),
        event_type=str(envelope["event_type"]),
        occurred_at=str(envelope["occurred_at"]),
        patient_id=str(envelope["patient_id"]),
        encounter_id=str(envelope["encounter_id"]),
        source=str(envelope["source"]),
        payload=dict(envelope["payload"]),
        tags=[event_type],
    )
    return append_event_registry_entry(entry, storage=storage)


def _write_his_summary(encounter: Dict[str, Any], *, storage: HisStorage) -> CurrentSummaryRecord:
    his_patient_id, his_encounter_id = _ensure_his_identifiers(encounter)
    triage = dict(encounter.get("triage", {}) or {})
    payload = {
        "public_encounter_id": encounter.get("encounter_id"),
        "triage": triage,
        "handoff_status": encounter.get("handoff_status", "NONE"),
        "final_state": encounter.get("final_state"),
        "state_trace": list(encounter.get("state_trace", [])),
        "recommended_handoff_target": _infer_default_handoff_target(encounter),
    }
    summary = CurrentSummaryRecord(
        encounter_id=his_encounter_id,
        patient_id=his_patient_id,
        summary_id=f"summary-{his_encounter_id}",
        current_state=str(encounter.get("final_state") or "STARTED"),
        payload=payload,
        source_memory_ids=[],
        updated_at=_utc_now_iso(),
    )
    return write_current_summary(summary, storage=storage)


def _sync_encounter_to_his(encounter: Dict[str, Any]) -> None:
    storage = _get_his_storage()
    his_patient_id, his_encounter_id = _ensure_his_identifiers(encounter)
    triage = dict(encounter.get("triage", {}) or {})
    ctas_level = f"L{triage.get('ctas_compat', 3)}"
    zone = derive_zone_from_ctas(ctas_level)

    register_patient(
        PatientRecord(
            patient_id=his_patient_id,
            full_name=str(encounter.get("patient_id") or "Unknown Patient"),
            identifiers={"public_patient_id": encounter.get("patient_id")},
        ),
        storage=storage,
    )
    his_open_encounter(
        EncounterRecord(
            patient_id=his_patient_id,
            encounter_id=his_encounter_id,
            status="OPEN",
            arrival_mode="walk-in",
            current_zone=zone,
            ctas_level=ctas_level,
            metadata={"public_encounter_id": encounter.get("encounter_id")},
        ),
        storage=storage,
    )
    record_triage(
        TriageRecord(
            encounter_id=his_encounter_id,
            patient_id=his_patient_id,
            triage_id=f"triage-{his_encounter_id}",
            ctas_level=ctas_level,
            zone=zone,
            summary=str(triage.get("acuity_ad", "C")),
            structured_data=triage,
        ),
        storage=storage,
    )
    vitals = dict(encounter.get("input_vitals", {}) or triage.get("vitals", {}) or {})
    if vitals:
        record_vital_signs(
            VitalSignsRecord(
                encounter_id=his_encounter_id,
                patient_id=his_patient_id,
                vital_id=f"vitals-{his_encounter_id}",
                readings=vitals,
            ),
            storage=storage,
        )
    _append_his_event(
        his_patient_id=his_patient_id,
        his_encounter_id=his_encounter_id,
        event_type="encounter_started",
        source="user_mode.start_encounter",
        payload={"triage": triage, "public_encounter_id": encounter.get("encounter_id")},
        storage=storage,
    )
    append_audit_log(
        AuditLogEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:12]}",
            action="encounter_started",
            actor="user_mode",
            patient_id=his_patient_id,
            encounter_id=his_encounter_id,
            details={"public_encounter_id": encounter.get("encounter_id")},
        ),
        storage=storage,
    )
    enqueue_outbox_event(
        event_type="ED_ENCOUNTER_STARTED",
        encounter_id=his_encounter_id,
        payload={"patient_id": his_patient_id, "public_encounter_id": encounter.get("encounter_id")},
        storage=storage,
    )
    _write_his_summary(encounter, storage=storage)


def _sync_handoff_request_to_his(encounter: Dict[str, Any], ticket: Dict[str, Any]) -> None:
    storage = _get_his_storage()
    his_patient_id, his_encounter_id = _ensure_his_identifiers(encounter)
    record = HandoffSnapshotRecord(
        snapshot_id=f"handoff-{ticket['handoff_ticket_id']}-requested",
        encounter_id=his_encounter_id,
        patient_id=his_patient_id,
        from_role="ED",
        to_role=str(ticket["target_system"]),
        handoff_stage="requested",
        patient_brief=str(ticket["reason"]),
        current_state={
            "public_encounter_id": encounter.get("encounter_id"),
            "public_ticket_id": ticket.get("handoff_ticket_id"),
            "final_state": encounter.get("final_state"),
        },
        pending_tasks=[{"task": "handoff_acceptance", "target_system": ticket["target_system"]}],
    )
    write_handoff_snapshot(record, storage=storage)
    _append_his_event(
        his_patient_id=his_patient_id,
        his_encounter_id=his_encounter_id,
        event_type="handoff_requested",
        source="user_mode.request_handoff",
        payload={"ticket_id": ticket["handoff_ticket_id"], "target_system": ticket["target_system"], "reason": ticket["reason"]},
        storage=storage,
    )
    append_audit_log(
        AuditLogEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:12]}",
            action="handoff_requested",
            actor="user_mode",
            patient_id=his_patient_id,
            encounter_id=his_encounter_id,
            details={"ticket_id": ticket["handoff_ticket_id"], "target_system": ticket["target_system"]},
        ),
        storage=storage,
    )
    enqueue_outbox_event(
        event_type=f"ED_PATIENT_READY_FOR_{ticket['target_system']}",
        encounter_id=his_encounter_id,
        payload={"patient_id": his_patient_id, "ticket_id": ticket["handoff_ticket_id"]},
        storage=storage,
    )
    _write_his_summary(encounter, storage=storage)


def _sync_handoff_completion_to_his(encounter: Dict[str, Any], ticket: Dict[str, Any]) -> None:
    storage = _get_his_storage()
    his_patient_id, his_encounter_id = _ensure_his_identifiers(encounter)
    handoff_stage = "completed" if ticket["status"] == "COMPLETED" else "requested"
    record = HandoffSnapshotRecord(
        snapshot_id=f"handoff-{ticket['handoff_ticket_id']}-completed",
        encounter_id=his_encounter_id,
        patient_id=his_patient_id,
        from_role="ED",
        to_role=str(ticket["receiver_system"] or ticket["target_system"]),
        handoff_stage=handoff_stage,
        patient_brief=str(ticket["reason"]),
        current_state={
            "public_encounter_id": encounter.get("encounter_id"),
            "public_ticket_id": ticket.get("handoff_ticket_id"),
            "final_state": encounter.get("final_state"),
            "receiver_bed": ticket.get("receiver_bed"),
        },
        completed_actions=[{"event": "handoff_completed", "status": ticket["status"]}],
    )
    write_handoff_snapshot(record, storage=storage)
    update_encounter_state(
        his_encounter_id,
        status=str(encounter.get("handoff_status", "COMPLETED")),
        current_zone=str(encounter.get("final_state") or "TRANSFER"),
        storage=storage,
    )
    record_clinical_assessment(
        ClinicalAssessmentRecord(
            encounter_id=his_encounter_id,
            patient_id=his_patient_id,
            assessment_id=f"assessment-{ticket['handoff_ticket_id']}",
            author_role="doctor",
            findings={"reason": ticket["reason"], "receiver_system": ticket["receiver_system"]},
        ),
        storage=storage,
    )
    record_diagnosis(
        DiagnosisRecord(
            encounter_id=his_encounter_id,
            patient_id=his_patient_id,
            diagnosis_id=f"dx-{ticket['handoff_ticket_id']}",
            label=str(encounter.get("final_state") or ticket["receiver_system"]),
            details={"handoff_status": ticket["status"]},
        ),
        storage=storage,
    )
    _append_his_event(
        his_patient_id=his_patient_id,
        his_encounter_id=his_encounter_id,
        event_type="handoff_completed",
        source="user_mode.complete_handoff",
        payload={
            "ticket_id": ticket["handoff_ticket_id"],
            "receiver_system": ticket["receiver_system"],
            "receiver_bed": ticket["receiver_bed"],
            "status": ticket["status"],
        },
        storage=storage,
    )
    append_audit_log(
        AuditLogEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:12]}",
            action="handoff_completed",
            actor="user_mode",
            patient_id=his_patient_id,
            encounter_id=his_encounter_id,
            details={"ticket_id": ticket["handoff_ticket_id"], "status": ticket["status"]},
        ),
        storage=storage,
    )
    enqueue_outbox_event(
        event_type="ED_HANDOFF_COMPLETED",
        encounter_id=his_encounter_id,
        payload={"patient_id": his_patient_id, "ticket_id": ticket["handoff_ticket_id"], "status": ticket["status"]},
        storage=storage,
    )
    _write_his_summary(encounter, storage=storage)


def _normalize_text(text: str) -> str:
    t = text.strip()
    for wrong, right in _SPELLING_FIXES.items():
        t = re.sub(rf"\b{re.escape(wrong)}\b", right, t, flags=re.IGNORECASE)
    return t


def _is_mostly_chinese(text: str) -> bool:
    if not text:
        return False
    chars = [c for c in text if c.strip()]
    if not chars:
        return False
    zh = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return zh / max(len(chars), 1) >= 0.2


def _session_lang(session: Dict[str, Any], fallback_text: str = "") -> str:
    shared = session.get("shared_memory", {}) if isinstance(session.get("shared_memory"), dict) else {}
    lang = str(shared.get("lang", "")).strip().lower()
    if lang in {"zh", "en"}:
        return lang
    return "zh" if _is_mostly_chinese(fallback_text) else "en"


def _is_smalltalk(text: str) -> bool:
    t = _normalize_text(text).strip().lower()
    if not t:
        return True
    if t in _SMALLTALK_PATTERNS:
        return True
    if re.fullmatch(r"(status|check queue|update)\??", t):
        return True
    return False


def _extract_vitals(text: str) -> Dict[str, float]:
    t = _normalize_text(text).lower()
    out: Dict[str, float] = {}
    spo2_match = re.search(r"(spo2|spo|氧饱和度|血氧|oxygen)[^\d]{0,8}(\d{2,3})", t)
    sbp_match = re.search(r"(sbp|收缩压|blood pressure|bp)[^\d]{0,8}(\d{2,3})", t)
    if spo2_match:
        out["spo2"] = float(spo2_match.group(2))
    if sbp_match:
        out["sbp"] = float(sbp_match.group(2))
    return out


def _extract_symptoms(text: str) -> List[str]:
    raw = _normalize_text(text).strip()
    if not raw or _is_smalltalk(raw):
        return []
    parts = [raw]
    for sep in [",", "，", ";", "；", "/", "|", " and "]:
        expanded: List[str] = []
        for p in parts:
            if sep in p:
                expanded.extend([x.strip() for x in p.split(sep) if x.strip()])
            else:
                expanded.append(p)
        parts = expanded

    inferred: List[str] = []
    lowered = raw.lower()
    for canonical, hints in _SYMPTOM_KEYWORDS.items():
        for h in hints:
            if h.lower() in lowered:
                inferred.append(canonical)
                break

    parts.extend(inferred)
    uniq: List[str] = []
    seen = set()
    for p in parts:
        if p.lower().startswith(("spo2", "sbp", "bp ")):
            continue
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def _extract_pain_score(text: str) -> Optional[int]:
    t = _normalize_text(text).lower()
    m = re.search(r"(pain|疼痛|痛感)[^\d]{0,8}(\d{1,2})", t)
    if not m:
        m = re.search(r"\b(\d{1,2})\s*/\s*10\b", t)
    if not m:
        return None
    v = int(m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1))
    if 0 <= v <= 10:
        return v
    return None


def _extract_duration(text: str) -> str:
    t = _normalize_text(text).lower()
    m_cn_rel = re.search(r"((\d+|半)\s*(分钟|小时|天)前)", t)
    if m_cn_rel:
        return m_cn_rel.group(1)
    m = re.search(r"(\d+\s*(minute|minutes|min|hour|hours|day|days|小时|分钟|天))", t)
    if m:
        return m.group(1)
    m_cn = re.search(r"(昨天(上午|中午|下午|晚上)?|今天(上午|中午|下午|晚上)?|今早|昨晚|前天|刚刚|方才)", t)
    if m_cn:
        return m_cn.group(1)
    # Common colloquial CN time-of-day without an explicit day marker.
    # Examples: "从早上开始", "上午开始", "昨晚开始" (handled above), etc.
    m_cn2 = re.search(r"(从\s*)?(早上|上午|中午|下午|晚上)(开始|起)?", t)
    if m_cn2:
        return m_cn2.group(2)
    m2 = re.search(r"(since (this morning|yesterday|last night|today))", t)
    if m2:
        return m2.group(1)
    m3 = re.search(r"\b(yesterday morning|yesterday afternoon|yesterday evening|last night|this morning|today)\b", t)
    if m3:
        return m3.group(1)
    return ""


def _extract_binary_answer(text: str) -> Optional[bool]:
    t = _normalize_text(text).strip().lower()
    if re.fullmatch(r"(yes|y|yeah|yep|correct|是|是的|对|对的|有|嗯|好的)", t):
        return True
    if re.fullmatch(r"(no|n|nope|不是|不|没有|无|否|否认)", t):
        return False
    return None


def _apply_targeted_short_answer(session: Dict[str, Any], msg: str) -> None:
    target = str(_doctor_runtime(session).get("active_target", "")).strip()
    if not target:
        return
    data = _doctor_data(session)
    yn = _extract_binary_answer(msg)
    if target == "duration":
        duration = _extract_duration(msg)
        if duration:
            data["duration"] = duration
        return
    if target in data.get("red_flags", {}) and yn is not None:
        data["red_flags"][target] = yn
        return
    if target in {"water_broken", "vaginal_bleeding", "urge_to_push"} and yn is not None:
        data["obstetric"][target] = yn
        return
    if target == "contraction_interval":
        duration = _extract_duration(msg)
        if duration:
            data["obstetric"]["contraction_interval"] = duration


def _extract_red_flags(text: str) -> Dict[str, Optional[bool]]:
    t = _normalize_text(text).lower()
    out: Dict[str, Optional[bool]] = {
        "fever": None,
        "breathing_difficulty": None,
        "worsening_pain": None,
        "syncope": None,
        "radiating_pain": None,
    }
    if re.search(r"\b(no fever|without fever|afebrile|deny fever|denies fever)\b|不发烧|没发烧|否认发热|无发热", t):
        out["fever"] = False
    elif "fever" in t or "发烧" in t or "发热" in t:
        out["fever"] = True

    if re.search(
        r"\b(no breathing difficulty|breathing is okay|no sob|no shortness of breath|deny sob|denies sob)\b|呼吸还好|不喘|没有呼吸困难|无呼吸困难|否认呼吸困难|不气促",
        t,
    ):
        out["breathing_difficulty"] = False
    elif "shortness of breath" in t or "dyspnea" in t or "呼吸困难" in t or "喘不上" in t or "气促" in t:
        out["breathing_difficulty"] = True

    if re.search(r"\b(not worsening|stable pain|not worse)\b|没有加重|未加重|差不多", t):
        out["worsening_pain"] = False
    elif "worsening pain" in t or "pain getting worse" in t or "越来越疼" in t or "明显更痛" in t or "加重" in t:
        out["worsening_pain"] = True

    if re.search(r"没有晕厥|无晕厥|否认晕厥|没有晕倒|无晕倒|否认晕倒|deny syncope|denies syncope", t):
        out["syncope"] = False
    elif "faint" in t or "syncope" in t or "晕厥" in t or "晕倒" in t:
        out["syncope"] = True
    if re.search(r"没有放射|无放射|否认放射|不放射|deny radiating", t):
        out["radiating_pain"] = False
    elif "radiat" in t or "jaw" in t or "arm" in t or "放射痛" in t or "放射到" in t:
        out["radiating_pain"] = True
    return out


def _explicit_worsening_negative(text: str) -> bool:
    t = _normalize_text(text).lower()
    return bool(re.search(r"\b(no worsening|not worsening|not worse|stable pain)\b|没有加重|未加重|不再加重|差不多", t))


def _nurse_measured_vitals(chief_complaint: str, symptoms: List[str]) -> Dict[str, float]:
    text = f"{chief_complaint} {' '.join(symptoms)}".lower()
    spo2 = 97.0
    sbp = 122.0
    if any(k in text for k in ["shortness of breath", "呼吸困难", "chest pain", "胸痛", "喘"]):
        spo2 = 94.0
        sbp = 128.0
    if any(k in text for k in ["dizzy", "dizziness", "syncope", "头晕", "晕厥"]):
        sbp = 105.0
    if any(k in text for k in ["severe", "worst", "very bad", "剧烈"]):
        sbp = 90.0
        spo2 = min(spo2, 92.0)
    return {"spo2": spo2, "sbp": sbp}


def _role_label(agent_code: str) -> str:
    mapping = {
        "TRIAGE_NURSE": "triage_nurse",
        "CALLING_NURSE": "calling_nurse",
        "DOCTOR": "doctor",
        "BEDSIDE_NURSE": "bed_nurse",
        "SYSTEM": "system",
        "PATIENT": "patient",
    }
    return mapping.get(agent_code, "system")


def _agent_reply(
    agent: str,
    fallback: str,
    session: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> str:
    context = {
        "phase": session.get("phase"),
        "call_status": session.get("call_status"),
        "queue_position": session.get("queue_position"),
        "estimated_wait_minutes": session.get("estimated_wait_minutes"),
        "movement_suggestion": session.get("movement_suggestion"),
        "shared_memory": session.get("shared_memory", {}),
    }
    if extra:
        context.update(extra)
    if not use_llm:
        return fallback
    return generate_clinical_reply(agent=agent, context=context, fallback=fallback)


def _require_type(payload: Dict[str, Any], key: str, expected: type) -> Any:
    if key not in payload:
        raise ApiError(f"Missing required field: {key}", error_code="MISSING_FIELD")
    value = payload[key]
    if not isinstance(value, expected):
        raise ApiError(
            f"Invalid type for field `{key}`: expected {expected.__name__}",
            error_code="INVALID_TYPE",
        )
    return value


def _from_payload_error(exc: PayloadError) -> ApiError:
    field_errors: List[Dict[str, str]] = []
    if exc.field:
        field_errors.append(
            {
                "field": exc.field,
                "error_code": exc.error_code,
                "message": exc.message,
            }
        )
    return ApiError(
        message=exc.message,
        status_code=400,
        error_code=exc.error_code,
        field_errors=field_errors,
    )


def _infer_default_handoff_target(encounter: Dict[str, Any]) -> str:
    triage = encounter["triage"]
    if triage["acuity_ad"] in {"A", "B"}:
        return "ICU"
    if triage["acuity_ad"] == "C":
        return "WARD"
    return "OUTPATIENT"


def _doctor_topic_plan(session: Dict[str, Any]) -> List[str]:
    memory = session.get("shared_memory", {})
    chief = str(memory.get("chief_complaint", "")).lower()
    symptoms = " ".join(memory.get("symptoms", [])).lower()
    merged = chief + " " + symptoms
    if any(k in merged for k in ["labor", "delivery", "giving birth", "分娩", "生小孩", "要生", "宫缩", "羊水", "破水", "pregnan"]):
        return ["duration", "water_broken", "contraction_interval", "vaginal_bleeding", "urge_to_push"]
    base = ["duration", "worsening_pain"]
    if "chest" in merged or "胸" in merged:
        base.extend(["breathing_difficulty", "radiating_pain", "syncope"])
    elif "dyspnea" in merged or "呼吸" in merged or "sob" in merged:
        base.extend(["breathing_difficulty", "fever"])
    elif "fever" in merged or "发烧" in merged:
        base.extend(["fever", "breathing_difficulty"])
    else:
        base.extend(["fever", "breathing_difficulty"])
    ordered = []
    seen = set()
    for item in base:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _extract_json_fragment(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _llm_extract_doctor_fields(session: Dict[str, Any], msg: str) -> Dict[str, Any]:
    prompt = (
        "Extract clinical slots from patient free text. "
        "Return JSON only with keys: "
        "{\"duration\":string|null,"
        "\"pain_score\":number|null,"
        "\"fever\":true|false|null,"
        "\"breathing_difficulty\":true|false|null,"
        "\"worsening_pain\":true|false|null,"
        "\"syncope\":true|false|null,"
        "\"radiating_pain\":true|false|null,"
        "\"water_broken\":true|false|null,"
        "\"vaginal_bleeding\":true|false|null,"
        "\"urge_to_push\":true|false|null,"
        "\"contraction_interval\":string|null}.\n"
        f"Context={json.dumps(session.get('shared_memory', {}), ensure_ascii=False)}\n"
        f"Patient message={msg}"
    )
    raw = generate_clinical_reply("DOCTOR_EXTRACTOR", {"phase": "DOCTOR_CALLED"}, prompt)
    parsed = _extract_json_fragment(raw)
    return parsed if isinstance(parsed, dict) else {}


def _doctor_runtime(session: Dict[str, Any]) -> Dict[str, Any]:
    return session.setdefault(
        "doctor_runtime",
        {
            "active_target": "",
            "retry_counts": {},
            "assumptions": [],
        },
    )


def _apply_best_effort_target(session: Dict[str, Any], target: str) -> None:
    data = _doctor_data(session)
    runtime = _doctor_runtime(session)
    if target == "duration":
        data["duration"] = data.get("duration") or "unknown"
    elif target in data.get("red_flags", {}):
        # In best-effort mode, default unresolved risk booleans to False but keep trace.
        data["red_flags"][target] = False
    elif target in data.get("obstetric", {}):
        if target == "contraction_interval":
            data["obstetric"][target] = data["obstetric"].get(target) or "unknown"
        else:
            data["obstetric"][target] = False
    runtime["assumptions"].append(
        {
            "target": target,
            "mode": "best_effort_default",
            "ts": _utc_now_iso(),
        }
    )


def _doctor_data(session: Dict[str, Any]) -> Dict[str, Any]:
    return session.setdefault(
        "doctor_data",
        {
            "duration": "",
            "pain_score": None,
            "red_flags": {
                "fever": None,
                "breathing_difficulty": None,
                "worsening_pain": None,
                "syncope": None,
                "radiating_pain": None,
            },
            "obstetric": {
                "water_broken": None,
                "vaginal_bleeding": None,
                "urge_to_push": None,
                "contraction_interval": "",
            },
            "informative_turns": 0,
        },
    )


def _extract_obstetric_fields(text: str) -> Dict[str, Any]:
    t = _normalize_text(text).lower()
    out: Dict[str, Any] = {
        "water_broken": None,
        "vaginal_bleeding": None,
        "urge_to_push": None,
        "contraction_interval": "",
    }
    if re.search(r"羊水破|破水|water broke|water broken|water break", t):
        out["water_broken"] = True
    if re.search(r"没(有)?破水|未破水|no water break|water not broke", t):
        out["water_broken"] = False
    if re.search(r"阴道出血|见红|bleeding|vaginal bleeding", t):
        out["vaginal_bleeding"] = True
    if re.search(r"没有出血|未出血|no bleeding", t):
        out["vaginal_bleeding"] = False
    if re.search(r"想用力|有便意|push|bearing down", t):
        out["urge_to_push"] = True
    if re.search(r"不想用力|no urge to push", t):
        out["urge_to_push"] = False
    interval = re.search(r"(\d+\s*(分钟|min|minute|minutes).{0,6}(一次|一阵|per))", t)
    if interval:
        out["contraction_interval"] = interval.group(1)
    return out


def _update_doctor_data(session: Dict[str, Any], msg: str) -> None:
    data = _doctor_data(session)
    # "yes/no" can be clinically informative if it's answering the doctor's active slot question.
    runtime = _doctor_runtime(session)
    active_target = str(runtime.get("active_target", "")).strip()
    binary = _extract_binary_answer(msg)
    duration_hint = _extract_duration(msg)
    pain_hint = _extract_pain_score(msg)
    informative = (not _is_smalltalk(msg)) or (
        bool(active_target) and (binary is not None or bool(duration_hint) or pain_hint is not None)
    )
    if informative:
        data["informative_turns"] = int(data.get("informative_turns", 0)) + 1
    _apply_targeted_short_answer(session, msg)
    duration = duration_hint
    if duration and not data.get("duration"):
        data["duration"] = duration
    pain = pain_hint
    if pain is not None:
        data["pain_score"] = pain
    old_flags = dict(data.get("red_flags", {}))
    flags = _extract_red_flags(msg)
    # If patient gives mixed info in one sentence, keep both timeline and progression.
    if "worsening_pain" in flags and flags.get("worsening_pain") is None:
        t = _normalize_text(msg).lower()
        if re.search(r"更重|加重|越来越", t):
            flags["worsening_pain"] = True
    for k, v in flags.items():
        if v is not None:
            data["red_flags"][k] = v
    ob = _extract_obstetric_fields(msg)
    for key in ["water_broken", "vaginal_bleeding", "urge_to_push"]:
        if isinstance(ob.get(key), bool):
            data["obstetric"][key] = ob[key]
    if isinstance(ob.get("contraction_interval"), str) and ob["contraction_interval"].strip():
        data["obstetric"]["contraction_interval"] = ob["contraction_interval"].strip()

    llm_slots = _llm_extract_doctor_fields(session, msg)
    if isinstance(llm_slots.get("duration"), str) and llm_slots["duration"].strip():
        data["duration"] = data.get("duration") or llm_slots["duration"].strip()
    if isinstance(llm_slots.get("pain_score"), (int, float)):
        score = int(llm_slots["pain_score"])
        if 0 <= score <= 10:
            data["pain_score"] = score
    for key in ["fever", "breathing_difficulty", "worsening_pain", "syncope", "radiating_pain"]:
        val = llm_slots.get(key)
        if isinstance(val, bool):
            if key == "worsening_pain" and old_flags.get(key) is True and val is False and not _explicit_worsening_negative(msg):
                continue
            if old_flags.get(key) is True and val is False and key != "worsening_pain":
                continue
            data["red_flags"][key] = val
    for key in ["water_broken", "vaginal_bleeding", "urge_to_push"]:
        val = llm_slots.get(key)
        if isinstance(val, bool):
            data["obstetric"][key] = val
    if isinstance(llm_slots.get("contraction_interval"), str) and llm_slots["contraction_interval"].strip():
        data["obstetric"]["contraction_interval"] = llm_slots["contraction_interval"].strip()

    # Keep doctor findings in shared memory for cross-agent continuity.
    session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
    session["shared_memory"]["doctor_assessment"]["doctor_data"] = data
    _memory_touch(session)


def _doctor_missing_topics(session: Dict[str, Any]) -> List[str]:
    data = _doctor_data(session)
    targets = _doctor_topic_plan(session)
    miss: List[str] = []
    if not data.get("duration"):
        miss.append("duration")
    for k in targets:
        if k == "duration":
            continue
        if k in data.get("red_flags", {}):
            if data.get("red_flags", {}).get(k) is None:
                miss.append(k)
        elif k in data.get("obstetric", {}):
            val = data.get("obstetric", {}).get(k)
            if isinstance(val, str):
                if not val.strip():
                    miss.append(k)
            elif val is None:
                miss.append(k)
    return miss


def _doctor_ready_for_disposition(session: Dict[str, Any]) -> bool:
    data = _doctor_data(session)
    # Stage2 disposition readiness is further gated by protocol-aware logic.
    # Keep this base gate simple to avoid old generic topic plans forcing unrelated questions.
    return int(data.get("informative_turns", 0)) >= 2


def _doctor_filled_slots(session: Dict[str, Any]) -> Dict[str, Any]:
    data = _doctor_data(session)
    filled: Dict[str, Any] = {}
    if data.get("duration"):
        filled["duration"] = data.get("duration")
    if data.get("pain_score") is not None:
        filled["pain_score"] = data.get("pain_score")
    for k, v in data.get("red_flags", {}).items():
        if v is not None:
            filled[k] = v
    for k, v in data.get("obstetric", {}).items():
        if isinstance(v, str):
            if v.strip():
                filled[k] = v
        elif v is not None:
            filled[k] = v
    return filled


def _update_stage2_trace(
    session: Dict[str, Any],
    *,
    retrieval_result: Dict[str, Any],
    evidence: Dict[str, Any],
    validated: Dict[str, Any],
    plan_contract: Dict[str, Any],
    llm_plan_raw: str = "",
) -> None:
    assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
    assess["active_protocol_ids"] = [retrieval_result.get("primary_protocol_id")] + list(
        retrieval_result.get("secondary_protocol_ids", [])
    )
    assess["normalized_complaints"] = list(retrieval_result.get("normalized_complaints", []))
    assess["filled_slots"] = _doctor_filled_slots(session)
    assess["missing_critical_slots"] = list(plan_contract.get("missing_critical_slots", []))
    assess["plan_contract"] = plan_contract
    assess["safety_floor"] = {
        "urgency_floor": plan_contract.get("urgency_floor"),
        "disposition_floor": plan_contract.get("disposition_floor"),
    }
    asked_ids = list(assess.get("asked_question_ids", []))
    qid = str(plan_contract.get("primary_question", {}).get("id", "")).strip()
    if qid and qid not in asked_ids:
        asked_ids.append(qid)
    assess["asked_question_ids"] = asked_ids
    denied = list(assess.get("denied_red_flags", []))
    for key, val in _doctor_data(session).get("red_flags", {}).items():
        if val is False and key not in denied:
            denied.append(key)
    assess["denied_red_flags"] = denied
    trace = list(assess.get("planner_trace", []))
    trace.append(
        {
            "ts": _utc_now_iso(),
            "primary_protocol_id": retrieval_result.get("primary_protocol_id"),
            "secondary_protocol_ids": retrieval_result.get("secondary_protocol_ids", []),
            "retrieval_score": retrieval_result.get("retrieval_score", 0.0),
            "evidence_refs": evidence.get("evidence_refs", []),
            "llm_plan_raw": llm_plan_raw,
            "validator_result": validated.get("validator_result", "pass"),
            "warning_codes": validated.get("warning_codes", []),
            "override_applied": validated.get("override_applied", False),
            "fallback_used": bool(retrieval_result.get("fallback_used")) or bool(validated.get("fallback_used")),
        }
    )
    assess["planner_trace"] = trace[-60:]
    assess["updated_at"] = _utc_now_iso()
    _memory_touch(session)


def _ensure_user_session() -> Dict[str, Any]:
    global _USER_MODE_SESSION
    if _USER_MODE_SESSION is None:
        _USER_MODE_SESSION = {
            "patient_id": "Patient 1",
            "phase": "INTAKE",
            "current_agent": "TRIAGE_NURSE",
            "encounter_id": None,
            "handoff_ticket_id": None,
            "transcript": [],
            "pending_messages": [],
            "phase_changed": False,
            "memory_version": 0,
            "required_data": {
                "chief_complaint": "",
                "symptoms": [],
                "vitals": {},
            },
            "doctor_data": {
                "duration": "",
                "pain_score": None,
                "red_flags": {
                    "fever": None,
                    "breathing_difficulty": None,
                    "worsening_pain": None,
                    "syncope": None,
                    "radiating_pain": None,
                },
                "obstetric": {
                    "water_broken": None,
                    "vaginal_bleeding": None,
                    "urge_to_push": None,
                    "contraction_interval": "",
                },
                "informative_turns": 0,
            },
            "shared_memory": {
                "chief_complaint": "",
                "symptoms": [],
                "vitals": {},
                "triage": {},
                "doctor_assessment": {},
                "handoff": {},
            },
            "call_status": "WAITING_FOR_TRIAGE",
            "queue_position": 0,
            "estimated_wait_minutes": 0,
            "movement_suggestion": {
                "target_zone": "triage_waiting_area",
                "instruction": "Please wait near triage waiting area.",
            },
            "auto_persona_name": None,
        }
    return _USER_MODE_SESSION


def _memory_touch(session: Dict[str, Any]) -> None:
    session["memory_version"] = int(session.get("memory_version", 0)) + 1


def _append_transcript(session: Dict[str, Any], agent: str, text: str) -> None:
    session["transcript"].append(
        {
            "timestamp": _utc_now_iso(),
            "role": _role_label(agent),
            "text": text,
        }
    )


def _enqueue_message(session: Dict[str, Any], role: str, text: str, event_type: str = "agent_prompt") -> None:
    item = {
        "role": role,
        "text": text,
        "ts": _utc_now_iso(),
        "event_type": event_type,
    }
    session.setdefault("pending_messages", []).append(item)


def _drain_pending_messages(session: Dict[str, Any]) -> List[Dict[str, str]]:
    raw = session.get("pending_messages", [])
    session["pending_messages"] = []
    out: List[Dict[str, str]] = []
    for msg in raw:
        out.append({"role": msg.get("role", "system"), "text": msg.get("text", "")})
    return out


def _remember_intake(session: Dict[str, Any], msg: str) -> None:
    req = session["required_data"]
    clean = _normalize_text(msg)
    if not req["chief_complaint"] and not _is_smalltalk(clean):
        req["chief_complaint"] = clean
    parsed_symptoms = _extract_symptoms(clean)
    if parsed_symptoms:
        req["symptoms"] = req["symptoms"] or parsed_symptoms
    elif req["chief_complaint"] and not req["symptoms"]:
        req["symptoms"] = _extract_symptoms(req["chief_complaint"])

    mem = session["shared_memory"]
    if req["chief_complaint"]:
        mem["chief_complaint"] = req["chief_complaint"]
    if req["symptoms"]:
        mem["symptoms"] = list(req["symptoms"])
    _memory_touch(session)


def _queue_metrics(session: Dict[str, Any]) -> Dict[str, int]:
    auto_snapshot = _load_auto_runtime_snapshot()
    encounter = _ENCOUNTERS.get(session.get("encounter_id")) if session.get("encounter_id") else None
    if (
        session["phase"] == "WAITING_CALL"
        and encounter is not None
        and auto_snapshot.get("available")
        and not _is_green_channel_encounter(encounter)
    ):
        triage = dict(session.get("shared_memory", {}).get("triage", {}) or {})
        ctas = int(triage.get("ctas_compat") or triage.get("level_1_4") or 3)
        priority_factor = float(auto_snapshot.get("priority_factor") or 2)
        user_priority = ctas * priority_factor
        queue_entries = list(auto_snapshot.get("doctor_queue_entries", []) or [])
        own_name = str(session.get("auto_persona_name") or "").strip()
        before_me = sum(
            1
            for entry in queue_entries
            if str(entry.get("name") or "").strip() != own_name
            and float(entry.get("priority", 9999)) <= user_priority
        )
        est_wait = max(0, before_me * (2 if ctas <= 2 else 5))
        return {
            "before_me": before_me,
            "estimated_wait_minutes": est_wait,
        }

    snap = queue_snapshot()
    before_me = 0
    if session["phase"] == "WAITING_CALL":
        before_me = max(0, int(snap.get("waiting_for_physician", 0)))
        enc_id = session.get("encounter_id")
        if enc_id and enc_id in _ENCOUNTERS:
            if _ENCOUNTERS[enc_id].get("final_state") == "WAITING_FOR_PHYSICIAN":
                before_me = max(0, before_me - 1)
    est_wait = before_me * 5
    if session.get("encounter_id") and session["encounter_id"] in _ENCOUNTERS:
        triage = _ENCOUNTERS[session["encounter_id"]]["triage"]
        if triage.get("level_1_4", 4) <= 2:
            est_wait = max(1, before_me * 2)
    return {"before_me": before_me, "estimated_wait_minutes": est_wait}


def _build_session_payload(session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_id": session["patient_id"],
        "phase": session["phase"],
        "current_agent": _role_label(session["current_agent"]),
        "call_status": session["call_status"],
        "queue_position": session["queue_position"],
        "estimated_wait_minutes": session["estimated_wait_minutes"],
        "encounter_id": session["encounter_id"],
        "handoff_ticket_id": session["handoff_ticket_id"],
        "movement_suggestion": session["movement_suggestion"],
        "memory_version": session.get("memory_version", 0),
    }


def _is_green_channel_encounter(encounter: Dict[str, Any]) -> bool:
    triage = encounter.get("triage", {}) if isinstance(encounter, dict) else {}
    hooks = set(triage.get("hooks", []) or [])
    if bool(triage.get("green_channel")):
        return True
    if triage.get("acuity_ad") in {"A", "B"}:
        return True
    if "abnormal_vitals" in hooks or "deterioration" in hooks:
        return True
    if encounter.get("final_state") == "UNDER_EVALUATION":
        return True
    return False


def _doctor_opening_from_memory(session: Dict[str, Any]) -> str:
    shared = session.get("shared_memory", {}) if isinstance(session.get("shared_memory"), dict) else {}
    chief = str(shared.get("chief_complaint", "")).strip()
    triage = shared.get("triage", {}) if isinstance(shared.get("triage"), dict) else {}
    acuity = str(triage.get("acuity_ad", "")).strip()
    lang = _session_lang(session, chief)
    if lang == "zh":
        if chief and acuity:
            return f"我已查看你的分诊记录：主诉为{chief}（分级 {acuity}）。请先告诉我症状是从什么时候开始的（例如半小时前、今天上午10点）。"
        if chief:
            return f"我已查看你的分诊记录：主诉为{chief}。请先告诉我症状是从什么时候开始的（例如半小时前、今天上午10点）。"
        return "我已查看你的分诊记录。请先告诉我症状是从什么时候开始的（例如半小时前、今天上午10点）。"
    if chief and acuity:
        return f"I reviewed your triage note: main complaint is {chief} (acuity {acuity}). Please tell me when the symptom started."
    if chief:
        return f"I reviewed your triage note: main complaint is {chief}. Please tell me when the symptom started."
    return "I reviewed your triage note. Please tell me when the symptom started."


def _doctor_disposition_summary(
    *,
    retrieval_result: Dict[str, Any],
    session: Dict[str, Any],
    target: str,
) -> str:
    protocol = str(retrieval_result.get("primary_protocol_id", "")).strip() or "general"
    data = _doctor_data(session)
    bits: List[str] = []
    if data.get("duration"):
        bits.append(f"onset: {data.get('duration')}")
    if data.get("pain_score") is not None:
        bits.append(f"pain_score: {data.get('pain_score')}/10")
    flags = data.get("red_flags", {})
    for key in ["worsening_pain", "breathing_difficulty", "syncope", "fever", "radiating_pain"]:
        val = flags.get(key)
        if val is True:
            bits.append(f"{key}: positive")
        elif val is False:
            bits.append(f"{key}: negative")
    core = "; ".join(bits[:4]) if bits else "limited but concerning data collected"
    return (
        f"Preliminary clinical impression: {protocol.replace('_', ' ')} pattern. "
        f"Key findings: {core}. "
        f"Current disposition plan: transfer to {target} for continued management."
    )


def _maybe_auto_progress(session: Dict[str, Any]) -> None:
    session["phase_changed"] = False

    if session["phase"] == "WAITING_CALL":
        queue = _queue_metrics(session)
        session["queue_position"] = queue["before_me"]
        session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
        if session["queue_position"] <= 0:
            session["phase_changed"] = True
            session["phase"] = "DOCTOR_CALLED"
            session["current_agent"] = "CALLING_NURSE"
            session["call_status"] = "CALLED"
            session["movement_suggestion"] = {
                "target_zone": "doctor_assessment_zone",
                "instruction": "Your number is called. Please go to doctor assessment zone now.",
            }
            _enqueue_message(
                session,
                "calling_nurse",
                f"{session['patient_id']}, your number is called. Please proceed to the doctor now.",
                event_type="number_called",
            )
            _sync_user_patient_to_auto(session, enqueue_doctor=False, user_phase="DOCTOR_CALLED")
            session["current_agent"] = "DOCTOR"
            doctor_line = _agent_reply(
                "DOCTOR",
                _doctor_opening_from_memory(session),
                session,
                use_llm=False,
            )
            _append_transcript(session, "DOCTOR", doctor_line)
            _enqueue_message(session, "doctor", doctor_line, event_type="agent_handoff")

    elif session["phase"] == "BED_NURSE_FLOW" and session.get("handoff_ticket_id"):
        session["phase_changed"] = True
        target_system = "ICU" if _ENCOUNTERS[session["encounter_id"]]["triage"]["acuity_ad"] in {"A", "B"} else "WARD"
        bed_number = f"{target_system}-BED-{str(session['patient_id']).split()[-1].zfill(2)}"
        complete = complete_handoff(
            {
                "handoff_ticket_id": session["handoff_ticket_id"],
                "receiver_system": target_system,
                "accepted": True,
                "receiver_bed": bed_number,
            }
        )
        session["phase"] = "DONE"
        session["call_status"] = "COMPLETED"
        session["current_agent"] = "BEDSIDE_NURSE"
        session["movement_suggestion"] = {
            "target_zone": "assigned_bed",
            "instruction": "Bed is arranged. Follow bedside nurse to assigned bed.",
        }
        session["shared_memory"]["handoff"] = complete
        _memory_touch(session)
        _sync_user_patient_to_auto(session, enqueue_doctor=False, user_phase="DONE")
        line = _agent_reply(
            "BEDSIDE_NURSE",
            (
                f"Bed arrangement done. Destination: {complete['final_disposition_state']}, "
                f"bed number {bed_number}, transfer latency {complete['transfer_latency_seconds']} seconds."
            ),
            session,
            extra={"handoff_result": complete},
            use_llm=False,
        )
        _append_transcript(session, "BEDSIDE_NURSE", line)
        _enqueue_message(session, "bed_nurse", line, event_type="agent_handoff")


def _doctor_next_question(topic: str, retry_count: int) -> str:
    direct = {
        "duration": "症状是从什么时候开始的？",
        "pain_score": "你现在疼痛评分是0到10分里的几分？",
        "fever": "你现在有发热吗？",
        "breathing_difficulty": "你现在有呼吸困难吗？",
        "worsening_pain": "和刚来时相比，现在是否更重了？",
        "syncope": "有没有晕厥、抽搐或意识模糊？",
        "radiating_pain": "疼痛有放射到手臂、下颌或背部吗？",
        "water_broken": "是否已经破水？",
        "contraction_interval": "宫缩现在大约几分钟一次？",
        "vaginal_bleeding": "现在有阴道出血吗？",
        "urge_to_push": "现在有明显想用力的感觉吗？",
    }
    clearer = {
        "duration": "我还需要更精确的时间线：例如“半小时前”“今天上午10点”“昨天上午”等，是什么时候开始的？",
        "pain_score": "请给一个数字：你现在疼痛是0到10分中的几分？",
        "fever": "请明确回答：现在有发热吗？",
        "breathing_difficulty": "请明确回答：现在有呼吸困难吗？",
        "worsening_pain": "请明确回答：和之前比是否更重了？",
        "syncope": "请明确回答：有没有晕厥、抽搐或意识模糊？",
        "radiating_pain": "请明确回答：疼痛是否放射到手臂、下颌或背部？",
        "water_broken": "请明确回答：是否已经破水？",
        "contraction_interval": "请给一个时间：宫缩大约几分钟一次？",
        "vaginal_bleeding": "请明确回答：现在有阴道出血吗？",
        "urge_to_push": "请明确回答：现在是否有明显想用力的感觉？",
    }
    if retry_count >= 1:
        return clearer.get(topic, "请用一句话明确回答这个问题。")
    return direct.get(topic, "请用一句话补充这个症状信息。")


def _ensure_single_question(candidate: str, fallback: str) -> str:
    text = (candidate or "").strip()
    if not text:
        return fallback
    first_line = text.splitlines()[0].strip()
    pieces = re.split(r"(?<=[?？])", first_line)
    if pieces:
        first_piece = pieces[0].strip()
        if "?" in first_piece or "？" in first_piece:
            return first_piece
    if "?" in fallback or "？" in fallback:
        return fallback
    return f"{fallback.rstrip('.。!！')}?"


def _question_sig(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def _pick_alternative_slot(plan_contract: Dict[str, Any], current_slot: str) -> str:
    missing = [str(x).strip() for x in plan_contract.get("missing_critical_slots", []) if str(x).strip()]
    for slot in missing:
        if slot != current_slot:
            return slot
    return current_slot


def _doctor_min_turns(primary_protocol_id: str, urgency_proposed: str) -> int:
    base = {
        "trauma": 4,
        "chest_pain": 4,
        "dyspnea": 4,
        "stroke": 4,
        "headache": 4,
        "sepsis": 4,
        "labor": 3,
    }.get(primary_protocol_id, 3)
    if urgency_proposed in {"URGENT", "RESUS"}:
        return max(base, 4)
    return base


def _doctor_ready_stage2(
    session: Dict[str, Any],
    *,
    retrieval_result: Dict[str, Any],
    plan_contract: Dict[str, Any],
) -> bool:
    data = _doctor_data(session)
    informative_turns = int(data.get("informative_turns", 0))
    primary_protocol = str(retrieval_result.get("primary_protocol_id", "")).strip()
    urgency = str(plan_contract.get("urgency_proposed", "ROUTINE")).upper()
    missing = list(plan_contract.get("missing_critical_slots", []))
    min_turns = _doctor_min_turns(primary_protocol, urgency)
    if informative_turns < min_turns:
        return False
    # For urgent/resus protocols, require all critical slots to be addressed.
    if urgency in {"URGENT", "RESUS"}:
        return len(missing) == 0
    return len(missing) <= 1


def _doctor_workflow_family(retrieval_result: Dict[str, Any]) -> str:
    p = str(retrieval_result.get("primary_protocol_id", "")).strip()
    if p == "chest_pain":
        return "chest_pain"
    if p in {"headache", "stroke"}:
        return "headache"
    if p in {"dizziness", "palpitations", "dyspnea"}:
        return "dizziness_palpitation"
    return "general"


def _mandatory_slots_for_family(family: str) -> List[str]:
    table = {
        "chest_pain": ["duration", "worsening_pain", "breathing_difficulty", "radiating_pain"],
        "headache": ["duration", "worsening_pain", "syncope"],
        "dizziness_palpitation": ["duration", "syncope", "breathing_difficulty"],
        "general": ["duration", "worsening_pain"],
    }
    return list(table.get(family, table["general"]))


def _mandatory_slots_complete(session: Dict[str, Any], family: str) -> bool:
    filled = _doctor_filled_slots(session)
    required = _mandatory_slots_for_family(family)
    return all((slot in filled and str(filled.get(slot, "")).strip() != "") for slot in required)


def _build_doctor_followup_line(
    session: Dict[str, Any],
    *,
    plan_contract: Dict[str, Any],
    retrieval_result: Dict[str, Any],
    evidence: Dict[str, Any],
    patient_message: str,
) -> str:
    runtime = _doctor_runtime(session)
    primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
    q = plan_contract.get("primary_question", {}) if isinstance(plan_contract.get("primary_question"), dict) else {}
    slot = str(q.get("slot", "")).strip()
    fallback = str(q.get("text", "")).strip() or "When did the symptom start?"

    # If we are stuck asking the same slot repeatedly, move to another unresolved slot.
    retry_counts = runtime.setdefault("retry_counts", {})
    if slot and int(retry_counts.get(slot, 0)) >= 2:
        alt_slot = _pick_alternative_slot(plan_contract, slot)
        if alt_slot and alt_slot != slot:
            fallback = _doctor_next_question(alt_slot, 0)
            slot = alt_slot

    llm_draft = _agent_reply(
        "DOCTOR",
        fallback,
        session,
        extra={
            "mode": "adaptive_single_question",
            "primary_protocol_id": primary,
            "secondary_protocol_ids": retrieval_result.get("secondary_protocol_ids", []),
            "next_slot": slot,
            "missing_critical_slots": plan_contract.get("missing_critical_slots", []),
            "evidence_refs": (evidence.get("evidence_refs", []) or [])[:4],
            "patient_message": patient_message,
            "instruction": (
                "Ask exactly one concise follow-up question tailored to the current complaint. "
                "Do not ask multiple questions in one turn. Do not repeat a question already answered."
            ),
        },
        use_llm=True,
    )
    line = _ensure_single_question(llm_draft, fallback)

    # Anti-loop: avoid emitting an identical question twice in a row.
    prev = str(runtime.get("last_question_text", "")).strip()
    if prev and _question_sig(prev) == _question_sig(line):
        alt_slot = _pick_alternative_slot(plan_contract, slot)
        if alt_slot and alt_slot != slot:
            line = _ensure_single_question(_doctor_next_question(alt_slot, 0), fallback)
            slot = alt_slot
        else:
            line = _ensure_single_question(_doctor_next_question(slot or "duration", 1), fallback)

    runtime["last_question_text"] = line
    runtime["active_target"] = slot
    return line


def _is_imaging_question(text: str) -> bool:
    t = _normalize_text(text).lower()
    has_question = ("?" in t) or ("？" in t) or ("should" in t) or ("要不要" in t) or ("应该" in t) or ("需不需要" in t)
    img_kw = ["影像", "扫描", "ct", "mri", "x-ray", "xray", "拍片", "超声", "b超"]
    return has_question and any(k in t for k in img_kw)


def _is_risk_anxiety_question(text: str) -> bool:
    t = _normalize_text(text).lower()
    has_question = ("?" in t) or ("？" in t) or ("吗" in t) or ("should" in t) or ("will" in t)
    risk_kw = ["会不会死", "会死吗", "很危险吗", "脑出血", "中风", "dying", "dangerous", "heart attack"]
    return has_question and any(k in t for k in risk_kw)


def _has_unanswered_patient_question(session: Dict[str, Any], msg: str) -> bool:
    assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
    pending = list(assess.get("pending_patient_questions", []) or [])
    answered = list(assess.get("answered_patient_questions", []) or [])
    if _is_imaging_question(msg):
        if "imaging" not in answered:
            pending.append("imaging")
    if _is_risk_anxiety_question(msg):
        if "risk" not in answered:
            pending.append("risk")
    # de-dup keep order
    seen = set()
    pending_clean = []
    for p in pending:
        if p not in seen:
            pending_clean.append(p)
            seen.add(p)
    assess["pending_patient_questions"] = pending_clean
    _memory_touch(session)
    return len(pending_clean) > 0


def _risk_anxiety_fallback_reply(primary_protocol_id: str, language: str) -> str:
    if language == "zh":
        if primary_protocol_id in {"headache", "stroke"}:
            return "我理解你的担心。我们会先排查危险信号并优先做必要检查，先确保安全。"
        if primary_protocol_id == "chest_pain":
            return "我理解你的担心。胸痛不一定是致命问题，但需要先排查高风险原因，我们会尽快评估。"
        return "我理解你的担心。当前会先排查高风险信号，并根据结果决定下一步。"
    return "I understand your concern. We will first rule out high-risk causes and prioritize urgent checks."


def _imaging_fallback_recommendation(primary_protocol_id: str, language: str) -> str:
    if primary_protocol_id in {"stroke", "headache"}:
        return "根据目前症状，通常先做头颅 CT；若需要进一步评估可追加 MRI。"
    if primary_protocol_id == "trauma":
        return "外伤场景通常先做受伤部位 X 光，必要时补充 CT。"
    if primary_protocol_id == "abdominal_pain":
        return "腹痛场景通常先做腹部超声，必要时再做腹部 CT。"
    if primary_protocol_id == "chest_pain":
        return "胸痛场景通常先做心电图和胸片，必要时再评估胸部 CT。"
    if language == "zh":
        return "是否做影像要看风险分层；目前可先做基础评估，再决定 CT / MRI / 超声。"
    return "Imaging depends on risk stratification; we can start with basic assessment and then choose CT/MRI/ultrasound."


def user_mode_chat_turn(message: str) -> Dict[str, Any]:
    if not isinstance(message, str) or not message.strip():
        raise ApiError("`message` is required and must be non-empty")

    session = _ensure_user_session()
    msg = message.strip()
    clean_msg = _normalize_text(msg)
    lang = "zh" if _is_mostly_chinese(msg) else "en"
    session.setdefault("shared_memory", {})["lang"] = lang
    _append_transcript(session, "PATIENT", msg)

    req = session["required_data"]
    req["vitals"].update(_extract_vitals(msg))
    pain = _extract_pain_score(msg)
    if pain is not None:
        req["vitals"]["pain_score"] = float(pain)
    if req.get("vitals"):
        session.setdefault("shared_memory", {})["vitals"] = dict(req["vitals"])
        _memory_touch(session)

    _maybe_auto_progress(session)

    if session["phase"] == "INTAKE":
        _remember_intake(session, msg)
        if not req["chief_complaint"]:
            ask = (
                "你好，我是分诊护士。正式分级前，请告诉我你今天主要哪里不舒服，严重程度 0-10 分是多少？"
                if lang == "zh"
                else "Hi, I’m the triage nurse for intake. Before formal triage scoring, what brought you in today and how severe is it from 0 to 10?"
            )
            session["current_agent"] = "TRIAGE_NURSE"
            session["call_status"] = "TRIAGE_INTAKE"
            _append_transcript(session, "TRIAGE_NURSE", ask)
            _enqueue_message(session, "triage_nurse", ask)
        else:
            session["phase"] = "CALL_NURSE_MEASURE"
            session["phase_changed"] = True
            session["current_agent"] = "CALLING_NURSE"
            session["call_status"] = "MEASURING_VITALS"
            session["movement_suggestion"] = {
                "target_zone": "vitals_station",
                "instruction": (
                    "请前往叫号护士站进行生命体征测量。"
                    if lang == "zh"
                    else "Please proceed to calling nurse station for vital measurement."
                ),
            }
            call_line = _agent_reply(
                "CALLING_NURSE",
                (
                    "我是叫号护士。现在为你测量生命体征，随后立刻送你去分诊。"
                    if lang == "zh"
                    else "I am the calling nurse. I will measure your vitals now and move you to triage immediately."
                ),
                session,
                extra={"chief_complaint": req["chief_complaint"], "symptoms": req["symptoms"]},
                use_llm=False,
            )
            _append_transcript(session, "CALLING_NURSE", call_line)
            _enqueue_message(session, "calling_nurse", call_line, event_type="agent_handoff")

    if session["phase"] == "CALL_NURSE_MEASURE":
        measured = _nurse_measured_vitals(req.get("chief_complaint", ""), req.get("symptoms", []))
        for k, v in measured.items():
            req["vitals"].setdefault(k, v)
        session["shared_memory"]["vitals"] = dict(req["vitals"])
        _memory_touch(session)

        measure_note = (
            f"生命体征已测量：SpO2 {int(req['vitals']['spo2'])}，SBP {int(req['vitals']['sbp'])}。现在送你去分诊。"
            if lang == "zh"
            else f"Vitals measured: SpO2 {int(req['vitals']['spo2'])}, SBP {int(req['vitals']['sbp'])}. Sending you to triage now."
        )
        _append_transcript(session, "CALLING_NURSE", measure_note)
        _enqueue_message(session, "calling_nurse", measure_note, event_type="measurement_completed")

        encounter = start_encounter(
            {
                "patient_id": session["patient_id"],
                "chief_complaint": req["chief_complaint"],
                "symptoms": req["symptoms"],
                "vitals": req["vitals"],
                "arrival_mode": "walk-in",
            }
        )
        session["encounter_id"] = encounter["encounter_id"]
        session["shared_memory"]["triage"] = encounter.get("triage", {})
        _memory_touch(session)

        triage_line = _agent_reply(
            "TRIAGE_NURSE",
            (
                f"Triage completed: acuity {encounter['triage']['acuity_ad']} "
                f"(CTAS {encounter['triage']['ctas_compat']})."
                if lang != "zh"
                else f"分诊完成：急诊分级 {encounter['triage']['acuity_ad']}（CTAS {encounter['triage']['ctas_compat']}）。"
            ),
            session,
            extra={"triage": encounter.get("triage", {})},
            use_llm=False,
        )
        _append_transcript(session, "TRIAGE_NURSE", triage_line)
        _enqueue_message(session, "triage_nurse", triage_line, event_type="triage_completed")

        if _is_green_channel_encounter(encounter):
            session["phase"] = "DOCTOR_CALLED"
            session["phase_changed"] = True
            session["current_agent"] = "DOCTOR"
            session["queue_position"] = 0
            session["estimated_wait_minutes"] = 0
            session["call_status"] = "CALLED"
            session["movement_suggestion"] = {
                "target_zone": "doctor_assessment_zone",
                "instruction": "Urgent triage channel activated. Please move to doctor assessment zone now.",
            }
            _sync_user_patient_to_auto(session, enqueue_doctor=False, user_phase="DOCTOR_CALLED")
            doctor_line = _agent_reply(
                "DOCTOR",
                _doctor_opening_from_memory(session),
                session,
                extra={"triage": encounter.get("triage", {})},
                use_llm=False,
            )
            _append_transcript(session, "DOCTOR", doctor_line)
            _enqueue_message(session, "doctor", doctor_line, event_type="agent_handoff")
        else:
            session["phase"] = "WAITING_CALL"
            session["phase_changed"] = True
            session["current_agent"] = "CALLING_NURSE"
            queue = _queue_metrics(session)
            session["queue_position"] = queue["before_me"]
            session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
            session["call_status"] = "WAITING_CALL"
            session["movement_suggestion"] = {
                "target_zone": "triage_waiting_area",
                "instruction": "Please wait in waiting room until your number is called.",
            }
            _sync_user_patient_to_auto(session, enqueue_doctor=True, user_phase="WAITING_CALL")
            if session["queue_position"] > 0:
                wait_line = _agent_reply(
                    "CALLING_NURSE",
                    (
                        f"你正在排队，前方约有 {session['queue_position']} 位患者，预计等待 {session['estimated_wait_minutes']} 分钟。"
                        if lang == "zh"
                        else f"You are in queue now. About {session['queue_position']} patients are before you, estimated wait {session['estimated_wait_minutes']} minutes."
                    ),
                    session,
                    use_llm=False,
                )
                _append_transcript(session, "CALLING_NURSE", wait_line)
                _enqueue_message(session, "calling_nurse", wait_line, event_type="queue_update")
            else:
                _maybe_auto_progress(session)

    elif session["phase"] == "WAITING_CALL":
        queue = _queue_metrics(session)
        session["queue_position"] = queue["before_me"]
        session["estimated_wait_minutes"] = queue["estimated_wait_minutes"]
        if session["queue_position"] > 0 and not _is_smalltalk(clean_msg):
            line = _agent_reply(
                "CALLING_NURSE",
                (
                    f"请稍候，前方还有 {session['queue_position']} 位患者，预计等待 {session['estimated_wait_minutes']} 分钟。"
                    if lang == "zh"
                    else f"Please wait. {session['queue_position']} patients are before you, estimated {session['estimated_wait_minutes']} minutes."
                ),
                session,
                use_llm=False,
            )
            _append_transcript(session, "CALLING_NURSE", line)
            _enqueue_message(session, "calling_nurse", line, event_type="queue_update")

    elif session["phase"] == "DOCTOR_CALLED":
        session["call_status"] = "IN_CONSULTATION"
        session["current_agent"] = "DOCTOR"
        runtime = _doctor_runtime(session)
        expected_target = str(runtime.get("active_target", "")).strip()
        _update_doctor_data(session, msg)
        retrieval_result = retrieve_protocols(
            chief_complaint=str(session.get("shared_memory", {}).get("chief_complaint", "")),
            symptoms=list(session.get("shared_memory", {}).get("symptoms", []) or []),
            patient_message=msg,
            vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
        )
        evidence = build_evidence_package(session, retrieval_result)
        plan_contract = build_doctor_plan(session=session, patient_message=msg, retrieval_result=retrieval_result)
        validated = validate_plan(
            plan_contract=plan_contract,
            retrieval_result=retrieval_result,
            vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
        )
        plan_contract = dict(validated.get("plan_contract", {}))
        missing_critical = list(plan_contract.get("missing_critical_slots", []))
        next_target = str(plan_contract.get("primary_question", {}).get("slot", "")).strip()

        # Doctor KB RAG bridge: only affects phrasing/explanations/extraction (never decisions).
        bridge_result = None
        try:
            primary_pid = str(retrieval_result.get("primary_protocol_id", "")).strip()
            kb_reg = registry_map()
            complaint_id = primary_pid if primary_pid in kb_reg else ""
            if not complaint_id:
                normalized = retrieval_result.get("normalized_complaints", []) or []
                if isinstance(normalized, list):
                    for item in normalized:
                        cid = str(item or "").strip()
                        if cid and cid in kb_reg:
                            complaint_id = cid
                            break
            if complaint_id and next_target:
                assess = session.get("shared_memory", {}).get("doctor_assessment", {}) if isinstance(session.get("shared_memory", {}), dict) else {}
                asked_ids = list((assess.get("asked_question_ids", []) or []))
                bridge_result = run_bridge(
                    complaint_id=complaint_id,
                    patient_text=msg,
                    language=str(plan_contract.get("language", "zh")).strip(),
                    next_slot=next_target,
                    filled_slots=_doctor_filled_slots(session),
                    asked_question_ids=asked_ids,
                )
                if getattr(bridge_result, "next_slot_echo", "") != next_target:
                    bridge_result = None
                else:
                    # Attach KB evidence refs so they appear in planner_trace.
                    if getattr(bridge_result, "evidence_refs", None):
                        evidence.setdefault("evidence_refs", [])
                        if isinstance(evidence.get("evidence_refs", None), list):
                            evidence["evidence_refs"].extend(list(bridge_result.evidence_refs))
        except Exception:
            bridge_result = None
        if next_target:
            runtime["active_target"] = next_target
            if next_target in missing_critical:
                retry_counts = runtime.setdefault("retry_counts", {})
                retry_counts[next_target] = int(retry_counts.get(next_target, 0)) + 1
                if retry_counts[next_target] > 2:
                    _apply_best_effort_target(session, next_target)
                    # Rebuild plan after best-effort defaulting.
                    plan_contract = build_doctor_plan(session=session, patient_message=msg, retrieval_result=retrieval_result)
                    validated = validate_plan(
                        plan_contract=plan_contract,
                        retrieval_result=retrieval_result,
                        vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
                    )
                    plan_contract = dict(validated.get("plan_contract", {}))
                    missing_critical = list(plan_contract.get("missing_critical_slots", []))
                    runtime["active_target"] = str(plan_contract.get("primary_question", {}).get("slot", "")).strip()
            elif expected_target == next_target:
                runtime.setdefault("retry_counts", {})[next_target] = 0

        _update_stage2_trace(
            session,
            retrieval_result=retrieval_result,
            evidence=evidence,
            validated=validated,
            plan_contract=plan_contract,
        )

        patient_question_priority = bool(_is_imaging_question(msg) or _is_risk_anxiety_question(msg))
        workflow_family = _doctor_workflow_family(retrieval_result)
        unanswered_patient_question = _has_unanswered_patient_question(session, msg)

        old_ready = _doctor_ready_for_disposition(session)
        if retrieval_result.get("fallback_used", False):
            # If we failed to retrieve a matching protocol, we must be MORE conservative,
            # otherwise a generic "what do you mean" turn can prematurely trigger WARD/ICU handoff.
            data = _doctor_data(session)
            informative_turns = int(data.get("informative_turns", 0))
            answered_flags = sum(
                1
                for v in (data.get("red_flags", {}) or {}).values()
                if isinstance(v, bool)
            )
            has_duration = bool(str(data.get("duration", "")).strip())
            ready_for_disposition = bool(old_ready and informative_turns >= 4 and has_duration and answered_flags >= 2)
        else:
            ready_for_disposition = bool(
                old_ready
                and _doctor_ready_stage2(
                    session,
                    retrieval_result=retrieval_result,
                    plan_contract=plan_contract,
                )
            )
        if patient_question_priority:
            ready_for_disposition = False
        if not _mandatory_slots_complete(session, workflow_family):
            ready_for_disposition = False
        if unanswered_patient_question:
            ready_for_disposition = False

        if not ready_for_disposition:
            if bridge_result is not None and getattr(bridge_result, "patient_explanation", ""):
                imaging_line = str(bridge_result.patient_explanation).strip()
                _append_transcript(session, "DOCTOR", imaging_line)
                _enqueue_message(session, "doctor", imaging_line, event_type="doctor_answer")
                assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
                pending = list(assess.get("pending_patient_questions", []) or [])
                assess["pending_patient_questions"] = [p for p in pending if p != "imaging"]
                answered = list(assess.get("answered_patient_questions", []) or [])
                if "imaging" not in answered:
                    answered.append("imaging")
                assess["answered_patient_questions"] = answered
                _memory_touch(session)
            elif _is_imaging_question(msg):
                # Legacy fallback when KB not available.
                primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
                lang = str(plan_contract.get("language", "zh")).strip()
                imaging_fallback = _imaging_fallback_recommendation(primary, lang)
                imaging_line = _agent_reply(
                    "DOCTOR",
                    imaging_fallback,
                    session,
                    extra={"mode": "patient_question_answer", "primary_protocol_id": primary, "patient_message": msg},
                    use_llm=True,
                )
                _append_transcript(session, "DOCTOR", imaging_line)
                _enqueue_message(session, "doctor", imaging_line, event_type="doctor_answer")
                assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
                pending = list(assess.get("pending_patient_questions", []) or [])
                assess["pending_patient_questions"] = [p for p in pending if p != "imaging"]
                answered = list(assess.get("answered_patient_questions", []) or [])
                if "imaging" not in answered:
                    answered.append("imaging")
                assess["answered_patient_questions"] = answered
                _memory_touch(session)
            elif _is_risk_anxiety_question(msg):
                primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
                lang = str(plan_contract.get("language", "zh")).strip()
                risk_line = _agent_reply(
                    "DOCTOR",
                    _risk_anxiety_fallback_reply(primary, lang),
                    session,
                    extra={"mode": "patient_risk_anxiety_answer", "primary_protocol_id": primary, "patient_message": msg},
                    use_llm=True,
                )
                _append_transcript(session, "DOCTOR", risk_line)
                _enqueue_message(session, "doctor", risk_line, event_type="doctor_answer")
                assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
                pending = list(assess.get("pending_patient_questions", []) or [])
                assess["pending_patient_questions"] = [p for p in pending if p != "risk"]
                answered = list(assess.get("answered_patient_questions", []) or [])
                if "risk" not in answered:
                    answered.append("risk")
                assess["answered_patient_questions"] = answered
                _memory_touch(session)

            if bridge_result is not None and getattr(bridge_result, "rendered_question", ""):
                line = _ensure_single_question(str(bridge_result.rendered_question), "When did it start?")
            else:
                line = _build_doctor_followup_line(
                    session,
                    plan_contract=plan_contract,
                    retrieval_result=retrieval_result,
                    evidence=evidence,
                    patient_message=msg,
                )
            _append_transcript(session, "DOCTOR", line)
            _enqueue_message(session, "doctor", line, event_type="doctor_followup")
        else:
            if _is_imaging_question(msg) or _is_risk_anxiety_question(msg):
                primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
                lang = str(plan_contract.get("language", "zh")).strip()
                answer = (
                    _imaging_fallback_recommendation(primary, lang)
                    if _is_imaging_question(msg)
                    else _risk_anxiety_fallback_reply(primary, lang)
                )
                answer_line = _agent_reply(
                    "DOCTOR",
                    answer,
                    session,
                    extra={"mode": "patient_question_answer_before_disposition", "primary_protocol_id": primary, "patient_message": msg},
                    use_llm=True,
                )
                _append_transcript(session, "DOCTOR", answer_line)
                _enqueue_message(session, "doctor", answer_line, event_type="doctor_answer")
                follow = _build_doctor_followup_line(
                    session,
                    plan_contract=plan_contract,
                    retrieval_result=retrieval_result,
                    evidence=evidence,
                    patient_message=msg,
                )
                _append_transcript(session, "DOCTOR", follow)
                _enqueue_message(session, "doctor", follow, event_type="doctor_followup")
                ready_for_disposition = False
            if not ready_for_disposition:
                pass
            else:
                encounter = _ENCOUNTERS.get(session["encounter_id"], {})
            triage = encounter.get("triage", {})
            acuity = triage.get("acuity_ad", "C")
            assess = session.setdefault("shared_memory", {}).setdefault("doctor_assessment", {})
            assess["doctor_data"] = _doctor_data(session)
            assess["assumptions"] = _doctor_runtime(session).get("assumptions", [])
            assess["updated_at"] = _utc_now_iso()
            _memory_touch(session)

            if acuity in {"A", "B", "C"}:
                target = "ICU" if acuity in {"A", "B"} else "WARD"
                ticket = request_handoff(
                    {
                        "encounter_id": session["encounter_id"],
                        "target_system": target,
                        "reason": "doctor disposition after assessment",
                    }
                )
                session["handoff_ticket_id"] = ticket["handoff_ticket_id"]
                session["phase"] = "BED_NURSE_FLOW"
                session["phase_changed"] = True
                session["current_agent"] = "BEDSIDE_NURSE"
                session["movement_suggestion"] = {
                    "target_zone": "bedside_transfer_zone",
                    "instruction": f"Proceed to bedside transfer area for {target} arrangement.",
                }
                _sync_user_patient_to_auto(session, enqueue_doctor=False, user_phase="BED_NURSE_FLOW")
                line = _agent_reply(
                    "DOCTOR",
                    _doctor_disposition_summary(
                        retrieval_result=retrieval_result,
                        session=session,
                        target=target,
                    ),
                    session,
                    extra={
                        "target_system": target,
                        "patient_message": msg,
                        "doctor_data": _doctor_data(session),
                        "retrieval_result": retrieval_result,
                    },
                    use_llm=False,
                )
                _append_transcript(session, "DOCTOR", line)
                _enqueue_message(session, "doctor", line, event_type="doctor_disposition")
                _maybe_auto_progress(session)
            else:
                session["phase"] = "DONE"
                session["phase_changed"] = True
                session["current_agent"] = "DOCTOR"
                session["call_status"] = "COMPLETED"
                session["movement_suggestion"] = {
                    "target_zone": "outpatient_exit",
                    "instruction": "You can proceed to outpatient follow-up.",
                }
                _sync_user_patient_to_auto(session, enqueue_doctor=False, user_phase="DONE")
                line = _agent_reply(
                    "DOCTOR",
                    (
                        "评估完成。请按门诊路径进行后续处理。"
                        if lang == "zh"
                        else "Assessment complete. Follow outpatient pathway for next management."
                    ),
                    session,
                    extra={"patient_message": msg},
                    use_llm=False,
                )
                _append_transcript(session, "DOCTOR", line)
                _enqueue_message(session, "doctor", line, event_type="doctor_disposition")

    elif session["phase"] == "BED_NURSE_FLOW":
        _maybe_auto_progress(session)

    else:
        if not _is_smalltalk(clean_msg):
            if _is_imaging_question(msg) or _is_risk_anxiety_question(msg):
                retrieval_result = retrieve_protocols(
                    chief_complaint=str(session.get("shared_memory", {}).get("chief_complaint", "")),
                    symptoms=list(session.get("shared_memory", {}).get("symptoms", []) or []),
                    patient_message=msg,
                    vitals=dict(session.get("shared_memory", {}).get("vitals", {}) or {}),
                )
                lang_done = _session_lang(session, msg)
                primary = str(retrieval_result.get("primary_protocol_id", "")).strip()
                reply = (
                    _imaging_fallback_recommendation(primary, lang_done)
                    if _is_imaging_question(msg)
                    else _risk_anxiety_fallback_reply(primary, lang_done)
                )
                _append_transcript(session, "DOCTOR", reply)
                _enqueue_message(session, "doctor", reply, event_type="doctor_answer")
                end_line = "本轮问诊已结束，如症状变化请重新开始问诊。"
                _append_transcript(session, "SYSTEM", end_line)
                _enqueue_message(session, "system", end_line, event_type="session_completed")
            else:
                line = "本轮问诊已结束，如症状变化请重新开始问诊。"
                _append_transcript(session, "SYSTEM", line)
                _enqueue_message(session, "system", line, event_type="session_completed")

    _maybe_auto_progress(session)
    pending_messages = list(session.get("pending_messages", []))
    messages = _drain_pending_messages(session)

    return {
        "session": _build_session_payload(session),
        "messages": messages,
        "pending_messages": pending_messages,
        "phase_changed": bool(session.get("phase_changed", False)),
        "transcript_tail": session["transcript"][-20:],
    }


def user_mode_session_status() -> Dict[str, Any]:
    session = _ensure_user_session()
    _maybe_auto_progress(session)
    pending_messages = list(session.get("pending_messages", []))
    messages = _drain_pending_messages(session)
    return {
        "session": _build_session_payload(session),
        "messages": messages,
        "pending_messages": pending_messages,
        "phase_changed": bool(session.get("phase_changed", False)),
        "transcript_tail": session["transcript"][-20:],
    }


def reset_user_mode_session() -> Dict[str, Any]:
    global _USER_MODE_SESSION
    _USER_MODE_SESSION = None
    session = _ensure_user_session()
    return {
        "session": _build_session_payload(session),
        "messages": [],
        "pending_messages": [],
        "phase_changed": False,
        "transcript_tail": [],
    }


def start_encounter(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cleaned = validate_encounter_start_payload(payload)
    except PayloadError as exc:
        raise _from_payload_error(exc) from exc

    patient_id = str(cleaned.get("patient_id", "")).strip() or f"patient-{uuid.uuid4().hex[:6]}"
    user_payload = {
        "patient_id": patient_id,
        "chief_complaint": cleaned["chief_complaint"],
        "symptoms": cleaned.get("symptoms", []),
        "vitals": cleaned["vitals"],
        "arrival_mode": cleaned["arrival_mode"],
    }
    result = run_user_mode(user_payload)
    if "error_code" in result:
        raise ApiError(
            result.get("message", "Encounter start failed"),
            status_code=400,
            error_code=str(result.get("error_code", "INVALID_REQUEST")),
            field_errors=result.get("field_errors") or [],
        )

    encounter_id = f"enc-{uuid.uuid4().hex[:10]}"
    created_at = _utc_now_iso()
    encounter = {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "input_vitals": dict(cleaned["vitals"]),
        "triage": result["triage"],
        "state_trace": result["state_trace"],
        "final_state": result["final_state"],
        "created_at": created_at,
        "updated_at": created_at,
        "handoff_status": "NONE",
    }
    _ENCOUNTERS[encounter_id] = encounter
    _sync_encounter_to_his(encounter)

    return {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "triage": result["triage"],
        "state_trace": result["state_trace"],
        "final_state": result["final_state"],
        "recommended_handoff_target": _infer_default_handoff_target(encounter),
        "status": "STARTED",
    }


def request_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    encounter_id = _require_type(payload, "encounter_id", str)
    reason = _require_type(payload, "reason", str).strip()
    target_system = _require_type(payload, "target_system", str).strip().upper()

    if target_system not in ALLOWED_RECEIVER_SYSTEMS:
        allowed = ", ".join(sorted(ALLOWED_RECEIVER_SYSTEMS))
        raise ApiError(f"Invalid `target_system`; allowed values: {allowed}")
    if encounter_id not in _ENCOUNTERS:
        raise ApiError(f"Unknown encounter_id: {encounter_id}", status_code=404)
    if not reason:
        raise ApiError("`reason` cannot be empty")

    encounter = _ENCOUNTERS[encounter_id]
    ticket_id = f"hdt-{uuid.uuid4().hex[:10]}"
    created_at = _utc_now_iso()
    ticket = {
        "handoff_ticket_id": ticket_id,
        "encounter_id": encounter_id,
        "patient_id": encounter["patient_id"],
        "status": "REQUESTED",
        "target_system": target_system,
        "reason": reason,
        "created_at": created_at,
        "accepted_at": None,
        "receiver_bed": None,
        "receiver_system": None,
    }
    _HANDOFF_TICKETS[ticket_id] = ticket

    encounter["handoff_status"] = "REQUESTED"
    encounter["updated_at"] = created_at
    encounter["last_handoff_ticket_id"] = ticket_id
    _sync_handoff_request_to_his(encounter, ticket)

    return {
        "handoff_ticket_id": ticket_id,
        "status": "REQUESTED",
        "event_type": f"ED_PATIENT_READY_FOR_{target_system}",
        "reason": reason,
    }


def complete_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    ticket_id = _require_type(payload, "handoff_ticket_id", str)
    receiver_system = _require_type(payload, "receiver_system", str).strip().upper()
    accepted = _require_type(payload, "accepted", bool)
    accepted_at = str(payload.get("accepted_at", _utc_now_iso()))
    receiver_bed = payload.get("receiver_bed")
    if receiver_bed is not None and not isinstance(receiver_bed, str):
        raise ApiError("`receiver_bed` must be a string when provided")

    if receiver_system not in ALLOWED_RECEIVER_SYSTEMS:
        allowed = ", ".join(sorted(ALLOWED_RECEIVER_SYSTEMS))
        raise ApiError(f"Invalid `receiver_system`; allowed values: {allowed}")
    if ticket_id not in _HANDOFF_TICKETS:
        raise ApiError(f"Unknown handoff_ticket_id: {ticket_id}", status_code=404)

    ticket = _HANDOFF_TICKETS[ticket_id]
    if ticket["status"] == "COMPLETED":
        raise ApiError(f"Handoff ticket already completed: {ticket_id}")

    if receiver_system != ticket["target_system"]:
        raise ApiError(
            f"receiver_system mismatch: expected {ticket['target_system']}, got {receiver_system}"
        )

    now_ts = _utc_now_iso()
    ticket["receiver_system"] = receiver_system
    ticket["accepted_at"] = accepted_at
    ticket["receiver_bed"] = receiver_bed
    ticket["status"] = "COMPLETED" if accepted else "REJECTED"

    encounter = _ENCOUNTERS[ticket["encounter_id"]]
    encounter["updated_at"] = now_ts
    if accepted:
        encounter["handoff_status"] = "COMPLETED"
        encounter["final_state"] = receiver_system
    else:
        encounter["handoff_status"] = "REJECTED"
        encounter["final_state"] = "AWAITING_DISPOSITION"
    _sync_handoff_completion_to_his(encounter, ticket)

    req_ts = _parse_iso(ticket["created_at"])
    done_ts = _parse_iso(accepted_at)
    latency = max(0, int((done_ts - req_ts).total_seconds()))

    return {
        "handoff_ticket_id": ticket_id,
        "status": ticket["status"],
        "final_disposition_state": encounter["final_state"],
        "transfer_latency_seconds": latency,
        "receiver_system": receiver_system,
        "receiver_bed": receiver_bed,
    }


def queue_snapshot() -> Dict[str, Any]:
    waiting_for_physician = 0
    under_evaluation = 0
    high_acuity_waiting = 0
    awaiting_handoff = 0
    active_encounters = 0

    for enc in _ENCOUNTERS.values():
        if enc["final_state"] not in {"OUTPATIENT", "ICU", "WARD", "LEAVE_ED"}:
            active_encounters += 1
        if enc["final_state"] == "WAITING_FOR_PHYSICIAN":
            waiting_for_physician += 1
            if enc["triage"]["level_1_4"] <= 2:
                high_acuity_waiting += 1
        if enc["final_state"] == "UNDER_EVALUATION":
            under_evaluation += 1
        if enc.get("handoff_status") == "REQUESTED":
            awaiting_handoff += 1

    requested = sum(1 for t in _HANDOFF_TICKETS.values() if t["status"] == "REQUESTED")
    completed = sum(1 for t in _HANDOFF_TICKETS.values() if t["status"] == "COMPLETED")
    rejected = sum(1 for t in _HANDOFF_TICKETS.values() if t["status"] == "REJECTED")

    result = {
        "total_encounters": len(_ENCOUNTERS),
        "active_encounters": active_encounters,
        "waiting_for_physician": waiting_for_physician,
        "under_evaluation": under_evaluation,
        "high_acuity_waiting": high_acuity_waiting,
        "awaiting_handoff": awaiting_handoff,
        "handoff": {
            "requested": requested,
            "completed": completed,
            "rejected": rejected,
            "total_tickets": len(_HANDOFF_TICKETS),
        },
    }
    auto_snapshot = _load_auto_runtime_snapshot()
    if auto_snapshot.get("available"):
        result["auto_runtime"] = {
            "sim_code": auto_snapshot.get("sim_code"),
            "doctor_global_queue": auto_snapshot.get("doctor_global_queue", 0),
            "triage_queue": auto_snapshot.get("triage_queue", 0),
            "priority_factor": auto_snapshot.get("priority_factor", 2),
        }
    return result


def reset_runtime_state() -> None:
    _ENCOUNTERS.clear()
    _HANDOFF_TICKETS.clear()
    global _USER_MODE_SESSION
    _USER_MODE_SESSION = None
