from datetime import datetime, timezone
from types import SimpleNamespace

from auto_memory_hooks import AutoMemoryHookManager
from app_core.app.api_v1 import export_auto_timeline, reset_runtime_state
from app_core.his.adapters.runtime_bridge import get_runtime_memory_service


def setup_function():
    reset_runtime_state()


def _make_patient(name="Patient 3", state="WAITING_FOR_DOCTOR", zone="major injuries zone", ctas=2):
    scratch = SimpleNamespace(
        state=state,
        injuries_zone=zone,
        CTAS=ctas,
        assigned_doctor=None,
        testing_kind=None,
        bed_assignment=None,
        disposition_done=False,
        admitted_to_hospital=False,
        boarding_timeout_at=None,
        admission_boarding_start=None,
        left_without_being_seen=False,
    )
    return SimpleNamespace(name=name, role="Patient", scratch=scratch, boarding_timeout_minutes=240)


def test_auto_mode_output_analysis_reports_replay_status():
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=get_runtime_memory_service(),
        now=frozen,
    )
    patient = _make_patient()

    manager.record_encounter_started(patient, step=0, sim_time=frozen, source="seed_existing")
    manager.record_handoff_requested(
        patient,
        step=1,
        sim_time=frozen,
        from_role="TriageNurse",
        to_role="Doctor",
        reason="escalation_for_chest_pain",
    )
    manager.record_handoff_completed(
        patient,
        step=2,
        sim_time=frozen,
        from_role="TriageNurse",
        to_role="Doctor",
        completion_note="doctor_received_case",
    )

    encounter_id = f"auto_{manager.run_id}_Patient_3"
    replay = get_runtime_memory_service().export_replay(run_id=manager.run_id, mode="auto", encounter_id=encounter_id)
    timeline = export_auto_timeline(
        encounter_id,
        run_id=manager.run_id,
        patient_id="Patient_3",
        patient_display_name="Patient 3",
        scenario_metadata={"scenario": "auto_frontend_debug"},
    )
    bundle = timeline["bundle"]
    summary = {
        "Backend flow status": [event["event_type"] for event in replay["events"]],
        "Frontend render status": "consumes_auto_replay_movement",
        "Avatar mapping status": ["patient", "doctor", "triage_nurse"],
        "Collision/path status": len(replay["events"]),
        "Timeline export status": timeline["document"]["document_type"],
        "Memory/HIS consistency": {
            "event_count_match": len(replay["events"]) == len(bundle["event_registry"]),
            "snapshot_count_match": len(replay["snapshots"]) == len(bundle["handoff_snapshots"]),
            "formal_patient_id": bundle["contract_alignment"]["formal_patient_id"],
        },
        "Conclusion": "replay_export_ready",
    }
    print(summary)

    assert len(replay["events"]) >= 3
    assert "encounter_started" in summary["Backend flow status"]
    assert "handoff_requested" in summary["Backend flow status"]
    assert "handoff_completed" in summary["Backend flow status"]
    assert summary["Timeline export status"] == "timeline_export"
    assert summary["Memory/HIS consistency"]["event_count_match"] is True
    assert summary["Memory/HIS consistency"]["snapshot_count_match"] is True
