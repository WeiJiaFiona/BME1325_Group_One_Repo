from __future__ import annotations

import json

from app_core.memory.schema import AuditRecord, CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem
from app_core.memory.storage import JsonFileMemoryStorage


def test_storage_appends_event_and_writes_current_summary(tmp_path):
    storage = JsonFileMemoryStorage(root=tmp_path / "runtime_data" / "memory")
    item = MemoryItem(
        memory_id="mem-1",
        run_id="auto_curr_sim_20260424_140753",
        mode="auto",
        encounter_id="auto_auto_curr_sim_20260424_140753_Patient_3",
        patient_id="Patient_3",
        step=3,
        sim_time=180,
        wall_time="2026-04-24T14:07:53+00:00",
        agent_role="bed_nurse",
        event_type="triage_completed",
        source="auto",
        priority="medium",
        content="Triage completed",
        structured_facts={"zone": "yellow"},
        tags=["triage"],
    )
    summary = CurrentEncounterSummary(
        run_id=item.run_id,
        mode=item.mode,
        encounter_id=item.encounter_id,
        patient_id=item.patient_id,
        current_state="WAITING_FOR_DOCTOR",
        current_zone="yellow",
        acuity="B",
        latest_vitals={"hr": 88},
        source_memory_ids=[item.memory_id],
        updated_at_step=3,
    )

    storage.append_event(item)
    storage.upsert_current_summary(summary)

    lines = storage.events_path.read_text(encoding="utf-8").strip().splitlines()
    stored_summary = storage.get_current_summary(item.run_id, item.mode, item.encounter_id)

    assert len(lines) == 1
    assert json.loads(lines[0])["event_type"] == "triage_completed"
    assert stored_summary == summary


def test_storage_writes_snapshot_and_audit(tmp_path):
    storage = JsonFileMemoryStorage(root=tmp_path / "runtime_data" / "memory")
    snapshot = HandoffMemorySnapshot(
        snapshot_id="snap-1",
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        patient_id="patient-123",
        from_role="doctor",
        to_role="ward",
        handoff_stage="completed",
        patient_brief="Stable for ward",
        current_state={"state": "DISPOSITION_DECIDED"},
        created_at_step=9,
    )
    audit = AuditRecord(
        op_id="audit-1",
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        op_type="write_snapshot",
        checkpoint="handoff_completed",
        source_ids=["mem-1"],
        top_k=1,
        latency_ms=12,
        details={"writer": "test"},
    )

    storage.write_snapshot(snapshot)
    storage.append_audit(audit)

    snapshot_files = list((storage.root / "snapshots").rglob("*.json"))
    audit_lines = storage.audits_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(snapshot_files) == 1
    assert json.loads(snapshot_files[0].read_text(encoding="utf-8"))["snapshot_id"] == "snap-1"
    assert json.loads(audit_lines[0])["op_type"] == "write_snapshot"
