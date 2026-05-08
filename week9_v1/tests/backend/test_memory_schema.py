from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app_core.memory.hooks import generate_auto_encounter_id, generate_auto_run_id, generate_user_run_id
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem, MemoryQuery


def test_memory_item_validates_and_serializes():
    item = MemoryItem(
        memory_id="mem-1",
        run_id="auto_curr_sim_20260424_140753",
        mode="auto",
        encounter_id="auto_auto_curr_sim_20260424_140753_Patient_3",
        patient_id="Patient_3",
        step=12,
        sim_time=720,
        wall_time="2026-04-24T14:07:53+00:00",
        agent_role="doctor",
        event_type="doctor_assessment_checkpoint",
        source="auto",
        priority="high",
        content="Doctor checkpoint recorded",
        structured_facts={"zone": "major injuries zone"},
        tags=["major", "doctor"],
        retrieval_scope=["handoff_requested"],
    )

    payload = item.to_dict()
    rebuilt = MemoryItem.from_dict(payload)

    assert rebuilt == item


def test_current_summary_validates():
    summary = CurrentEncounterSummary(
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        patient_id="patient-123",
        current_state="WAITING_FOR_DOCTOR",
        current_zone="yellow",
        acuity="B",
        latest_vitals={"hr": 98},
        active_risks=[{"risk": "sepsis"}],
        pending_tasks=[{"task": "doctor reassessment"}],
        completed_actions=[{"action": "triage completed"}],
        latest_doctor_findings={"impression": "observe"},
        latest_test_status={"lab": "pending"},
        source_memory_ids=["mem-1"],
        updated_at_step=7,
    )

    assert summary.to_dict()["patient_id"] == "patient-123"


def test_handoff_snapshot_validates():
    snapshot = HandoffMemorySnapshot(
        snapshot_id="snap-1",
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        patient_id="patient-123",
        from_role="doctor",
        to_role="bed_nurse",
        handoff_stage="requested",
        patient_brief="Patient needs monitoring",
        current_state={"state": "WAITING_FOR_RESULT"},
        completed_actions=[{"action": "triage"}],
        pending_tasks=[{"task": "monitor vitals"}],
        active_risks=[{"risk": "unstable blood pressure"}],
        next_actions=[{"action": "repeat blood pressure"}],
        source_memory_ids=["mem-1", "mem-2"],
        created_at_step=10,
    )

    assert snapshot.to_dict()["handoff_stage"] == "requested"


def test_memory_query_enforces_bounds():
    with pytest.raises(ValueError, match="top_k"):
        MemoryQuery(
            run_id="auto_curr_sim_20260424_140753",
            mode="auto",
            encounter_id="auto_auto_curr_sim_20260424_140753_Patient_3",
            checkpoint="handoff_requested",
            top_k=6,
        )


def test_auto_and_user_id_generation_rules_are_stable():
    frozen = datetime(2026, 4, 24, 14, 7, 53, tzinfo=timezone.utc)

    auto_run_id = generate_auto_run_id("curr_sim", now=frozen)
    user_run_id = generate_user_run_id(now=frozen)
    encounter_id = generate_auto_encounter_id(auto_run_id, "Patient 3")

    assert auto_run_id == "auto_curr_sim_20260424_140753"
    assert user_run_id == "user_20260424_140753"
    assert encounter_id == "auto_auto_curr_sim_20260424_140753_Patient_3"
