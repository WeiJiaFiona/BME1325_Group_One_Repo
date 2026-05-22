from __future__ import annotations

from app_core.his.adapters.memory_adapter import (
    get_memory_to_his_mapping_expectation,
    get_memory_upgrade_plan,
    persist_current_summary_to_his,
    persist_handoff_snapshot_to_his,
    persist_memory_item_to_his,
)
from app_core.his.config import generate_encounter_id, generate_patient_id
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage
from app_core.memory.hooks import build_handoff_snapshot_id, build_memory_event
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem


def test_memory_upgrade_expectation_tracks_frozen_inputs() -> None:
    expectation = get_memory_to_his_mapping_expectation()
    assert expectation.accepted_inputs == (
        MemoryItem,
        CurrentEncounterSummary,
        HandoffMemorySnapshot,
    )


def test_memory_upgrade_plan_uses_frozen_his_targets_only() -> None:
    targets = {plan.target_table for plan in get_memory_upgrade_plan()}
    assert {"memory_events", "event_registry", "current_encounter_summaries", "handoff_snapshots", "clinical_documents"} <= targets


def test_memory_upgrade_path_persists_event_summary_and_handoff(tmp_path) -> None:
    storage = SQLiteDevHisStorage(db_path=tmp_path / "memory_upgrade.sqlite3")
    storage.bootstrap()
    patient_id = generate_patient_id()
    encounter_id = generate_encounter_id()
    memory_item = build_memory_event(
        run_id="user_20260508_120000",
        mode="user",
        encounter_id=encounter_id,
        patient_id=patient_id,
        step=0,
        agent_role="triage_nurse",
        event_type="triage_completed",
        source="tests_his",
        priority="routine",
        content="Triage normalized to L2 / orange.",
        structured_facts={"ctas_level": "L2", "zone": "orange"},
    )
    summary = CurrentEncounterSummary(
        run_id="user_20260508_120000",
        mode="user",
        encounter_id=encounter_id,
        patient_id=patient_id,
        current_state="awaiting_doctor",
        current_zone="orange",
        acuity="L2",
        latest_vitals={"spo2": 94, "sbp": 102},
        pending_tasks=[{"task": "doctor_assessment"}],
        source_memory_ids=[memory_item.memory_id],
        updated_at_step=1,
    )
    snapshot = HandoffMemorySnapshot(
        snapshot_id=build_handoff_snapshot_id("user_20260508_120000", encounter_id, "requested"),
        run_id="user_20260508_120000",
        mode="user",
        encounter_id=encounter_id,
        patient_id=patient_id,
        from_role="doctor",
        to_role="bed_nurse",
        handoff_stage="requested",
        patient_brief="Chest pain pending ICU transfer.",
        current_state={"ctas_level": "L2", "zone": "orange"},
        pending_tasks=[{"task": "transfer"}],
        source_memory_ids=[memory_item.memory_id],
        created_at_step=2,
    )
    stored_event = persist_memory_item_to_his(memory_item, storage=storage)
    stored_summary = persist_current_summary_to_his(summary, storage=storage)
    stored_snapshot, stored_document, stored_registry = persist_handoff_snapshot_to_his(snapshot, storage=storage)
    assert stored_event.event_type == "triage_completed"
    assert storage.list_events(encounter_id)[0].event_id == stored_event.event_id
    assert storage.get_current_summary(encounter_id).summary_id == stored_summary.summary_id
    assert storage.get_handoff_snapshots(encounter_id)[0].snapshot_id == stored_snapshot.snapshot_id
    assert storage.list_documents(encounter_id)[0].document_id == stored_document.document_id
    assert stored_registry.document_id == stored_document.document_id
