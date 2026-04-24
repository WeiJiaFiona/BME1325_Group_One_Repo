from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from .schema import AuditRecord, HandoffMemorySnapshot, MemoryItem, utc_now_iso


def _safe_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def _timestamp_token(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    return current.strftime("%Y%m%d_%H%M%S")


def generate_auto_run_id(sim_code: str, *, now: datetime | None = None) -> str:
    return f"auto_{_safe_token(sim_code)}_{_timestamp_token(now)}"


def generate_user_run_id(*, now: datetime | None = None) -> str:
    return f"user_{_timestamp_token(now)}"


def generate_auto_encounter_id(run_id: str, patient_name: str) -> str:
    return f"auto_{run_id}_{_safe_token(patient_name)}"


def next_memory_step(current_step: int | None = None) -> int:
    if current_step is None:
        return 0
    return int(current_step) + 1


def build_memory_event(
    *,
    run_id: str,
    mode: str,
    encounter_id: str,
    patient_id: str,
    step: int,
    agent_role: str,
    event_type: str,
    source: str,
    priority: str | int,
    content: str,
    structured_facts: dict | None = None,
    state_before: dict | None = None,
    state_after: dict | None = None,
    tags: list[str] | None = None,
    salience: float | int | None = None,
    retrieval_scope: list[str] | None = None,
    sim_time: float | int | None = None,
    wall_time: str | None = None,
    memory_id: str | None = None,
) -> MemoryItem:
    return MemoryItem(
        memory_id=memory_id or f"mem-{uuid4().hex[:12]}",
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=step,
        sim_time=sim_time,
        wall_time=wall_time or utc_now_iso(),
        agent_role=agent_role,
        event_type=event_type,
        source=source,
        priority=priority,
        content=content,
        structured_facts=structured_facts or {},
        state_before=state_before,
        state_after=state_after,
        tags=tags or [],
        salience=salience,
        retrieval_scope=retrieval_scope,
    )


def build_handoff_snapshot_id(run_id: str, encounter_id: str, stage: str) -> str:
    return f"snap_{_safe_token(run_id)}_{_safe_token(encounter_id)}_{_safe_token(stage)}_{uuid4().hex[:8]}"


def build_audit_record(
    *,
    run_id: str,
    mode: str,
    encounter_id: str,
    op_type: str,
    checkpoint: str,
    source_ids: list[str] | None = None,
    top_k: int | None = None,
    latency_ms: float | int | None = None,
    details: dict | None = None,
) -> AuditRecord:
    return AuditRecord(
        op_id=f"audit-{uuid4().hex[:12]}",
        run_id=run_id,
        mode=mode,
        encounter_id=encounter_id,
        op_type=op_type,
        checkpoint=checkpoint,
        source_ids=source_ids or [],
        top_k=top_k,
        latency_ms=latency_ms,
        details=details or {},
    )
