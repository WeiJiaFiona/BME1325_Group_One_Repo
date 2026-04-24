import os


def test_memory_service_disabled_is_fail_open(tmp_path):
    from app_core.memory.service import create_memory_service
    from app_core.memory.hooks import build_memory_event
    from app_core.memory.schema import MemoryQuery

    old = os.environ.get("MEMORY_V1_ENABLED")
    try:
        os.environ["MEMORY_V1_ENABLED"] = "0"
        os.environ["MEMORY_V1_ROOT"] = str(tmp_path / "runtime_data" / "memory")
        service = create_memory_service()
        assert service.enabled is False

        result = service.append_event(
            build_memory_event(
                run_id="user_test",
                mode="user",
                encounter_id="enc-test",
                patient_id="patient-1",
                step=1,
                agent_role="system",
                event_type="encounter_started",
                source="user",
                priority="low",
                content="start",
            )
        )
        assert result is None
        assert service.retrieve(
            MemoryQuery(run_id="user_test", mode="user", encounter_id="enc-test", checkpoint="replay_export")
        ) == []
    finally:
        if old is None:
            os.environ.pop("MEMORY_V1_ENABLED", None)
        else:
            os.environ["MEMORY_V1_ENABLED"] = old


def test_json_storage_round_trip_replay_export(tmp_path):
    from app_core.memory.hooks import build_audit_record, build_handoff_snapshot_id, build_memory_event
    from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot
    from app_core.memory.service import create_memory_service

    os.environ["MEMORY_V1_ENABLED"] = "1"
    os.environ["MEMORY_V1_ROOT"] = str(tmp_path / "runtime_data" / "memory")

    service = create_memory_service()
    event = build_memory_event(
        run_id="user_test",
        mode="user",
        encounter_id="enc-test",
        patient_id="patient-1",
        step=1,
        agent_role="doctor",
        event_type="handoff_requested",
        source="user",
        priority="high",
        content="handoff requested",
        tags=["handoff"],
    )
    service.append_event(event)
    service.update_current_summary(
        CurrentEncounterSummary(
            run_id="user_test",
            mode="user",
            encounter_id="enc-test",
            patient_id="patient-1",
            current_state="BED_NURSE_FLOW",
            current_zone="yellow",
            acuity="C",
            source_memory_ids=[event.memory_id],
            updated_at_step=1,
        )
    )
    snapshot = HandoffMemorySnapshot(
        snapshot_id=build_handoff_snapshot_id("user_test", "enc-test", "requested"),
        run_id="user_test",
        mode="user",
        encounter_id="enc-test",
        patient_id="patient-1",
        from_role="doctor",
        to_role="ward",
        handoff_stage="requested",
        patient_brief="need bed",
        current_state={"state": "BED_NURSE_FLOW"},
        source_memory_ids=[event.memory_id],
        created_at_step=1,
    )
    service.write_handoff_snapshot(snapshot)
    service.append_audit(
        build_audit_record(
            run_id="user_test",
            mode="user",
            encounter_id="enc-test",
            op_type="write_snapshot",
            checkpoint="handoff_requested",
            source_ids=[event.memory_id],
            details={"test": True},
        )
    )

    replay = service.export_replay(run_id="user_test", mode="user", encounter_id="enc-test")
    assert len(replay["events"]) == 1
    assert len(replay["summaries"]) == 1
    assert len(replay["snapshots"]) == 1
    assert len(replay["audits"]) == 1
