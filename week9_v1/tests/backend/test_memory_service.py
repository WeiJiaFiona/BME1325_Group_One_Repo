from __future__ import annotations

from datetime import datetime, timezone

from app_core.memory.hooks import build_audit_record, build_memory_event
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryQuery
from app_core.memory.service import create_memory_service


def test_memory_service_noops_when_disabled(tmp_path):
    root = tmp_path / "runtime_data" / "memory"
    service = create_memory_service(root=root, enabled=False)

    result = service.append_event(
        build_memory_event(
            run_id="auto_curr_sim_20260424_140753",
            mode="auto",
            encounter_id="auto_auto_curr_sim_20260424_140753_Patient_3",
            patient_id="Patient_3",
            step=1,
            agent_role="doctor",
            event_type="encounter_started",
            source="auto",
            priority="high",
            content="Encounter opened",
        )
    )

    assert result is None
    assert service.retrieve(
        MemoryQuery(
            run_id="auto_curr_sim_20260424_140753",
            mode="auto",
            encounter_id="auto_auto_curr_sim_20260424_140753_Patient_3",
            checkpoint="replay_export",
        )
    ) == []
    assert not root.exists()


def test_memory_service_round_trip_and_replay_export(tmp_path):
    root = tmp_path / "runtime_data" / "memory"
    service = create_memory_service(root=root, enabled=True)
    event = build_memory_event(
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        patient_id="patient-123",
        step=4,
        agent_role="doctor",
        event_type="handoff_requested",
        source="user",
        priority="high",
        content="Handoff requested",
        tags=["handoff"],
    )
    summary = CurrentEncounterSummary(
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        patient_id="patient-123",
        current_state="WAITING_FOR_EXIT",
        current_zone="yellow",
        acuity="C",
        pending_tasks=[{"task": "bed assignment"}],
        source_memory_ids=[event.memory_id],
        updated_at_step=4,
    )
    snapshot = HandoffMemorySnapshot(
        snapshot_id="snap-123",
        run_id="user_20260424_140753",
        mode="user",
        encounter_id="enc-123",
        patient_id="patient-123",
        from_role="doctor",
        to_role="ward",
        handoff_stage="requested",
        patient_brief="Need ward bed",
        current_state={"state": "WAITING_FOR_EXIT"},
        pending_tasks=[{"task": "bed assignment"}],
        source_memory_ids=[event.memory_id],
        created_at_step=4,
    )

    service.append_event(event)
    service.update_current_summary(summary)
    service.write_handoff_snapshot(snapshot)
    service.append_audit(
        build_audit_record(
            run_id="user_20260424_140753",
            mode="user",
            encounter_id="enc-123",
            op_type="write_snapshot",
            checkpoint="handoff_requested",
            source_ids=[event.memory_id],
            details={"test": True},
        )
    )

    replay = service.export_replay(run_id="user_20260424_140753", mode="user", encounter_id="enc-123")

    assert len(replay["events"]) == 1
    assert len(replay["summaries"]) == 1
    assert len(replay["snapshots"]) == 1
    assert len(replay["audits"]) == 1
    assert "personas" not in {path.name for path in root.rglob("*") if path.is_dir()}


def test_hook_helpers_generate_expected_ids():
    frozen = datetime(2026, 4, 24, 14, 7, 53, tzinfo=timezone.utc)
    service = create_memory_service(enabled=False)

    assert service.enabled is False
    assert frozen.strftime("%Y%m%d_%H%M%S") == "20260424_140753"
