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


def _make_server(patient):
    maze = SimpleNamespace(
        patients_waiting_for_doctor=[[2, patient.name]],
        doctors_taking_more_patients=[],
        injuries_zones={
            "bedside_nurse_waiting": [[2, patient.name]],
        },
    )
    return SimpleNamespace(
        maze=maze,
        personas={patient.name: patient},
        doctor_starting_amount=1,
        bedside_starting_amount=1,
    )


def test_auto_timeline_analysis_reports_boarding_and_bottleneck():
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=get_runtime_memory_service(),
        now=frozen,
    )
    patient = _make_patient(state="ADMITTED_BOARDING")
    patient.scratch.boarding_timeout_at = frozen
    patient.scratch.admission_boarding_start = frozen
    manager.record_encounter_started(patient, step=0, sim_time=frozen, source="seed_existing")
    manager.record_boarding_timeout(patient, step=5, sim_time=frozen)
    manager.record_resource_bottlenecks(_make_server(patient), step=6, sim_time=frozen)

    encounter_id = f"auto_{manager.run_id}_Patient_3"
    timeline = export_auto_timeline(
        encounter_id,
        run_id=manager.run_id,
        patient_id="Patient_3",
        patient_display_name="Patient 3",
        scenario_metadata={"scenario": "boarding_bottleneck"},
    )
    bundle = timeline["bundle"]
    events = [event["event_type"] for event in bundle["memory_replay"]["events"]]
    summary = {
        "Backend flow status": events,
        "Frontend render status": "consumes_auto_replay_movement",
        "Avatar mapping status": ["patient", "doctor", "bed_nurse"],
        "Collision/path status": len(events),
        "Timeline export status": timeline["document"]["document_type"],
        "Memory/HIS consistency": len(bundle["event_registry"]) == len(bundle["memory_replay"]["events"]),
        "Conclusion": bundle["scenario_metadata"]["scenario"],
    }
    print(summary)

    assert "boarding_timeout" in events
    assert "resource_bottleneck" in events
    assert summary["Timeline export status"] == "timeline_export"
    assert summary["Memory/HIS consistency"] is True


def test_auto_timeline_analysis_reports_surge_patient_set():
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=get_runtime_memory_service(),
        now=frozen,
    )
    patients = [_make_patient(name=f"Patient {idx}") for idx in range(1, 4)]
    for idx, patient in enumerate(patients):
        manager.record_encounter_started(patient, step=idx, sim_time=frozen, source="surge_seed")

    encounter_id = f"auto_{manager.run_id}_Patient_1"
    timeline = export_auto_timeline(
        encounter_id,
        run_id=manager.run_id,
        patient_id="Patient_1",
        patient_display_name="Patient 1",
        scenario_metadata={"scenario": "surge", "persona_names": [patient.name for patient in patients]},
    )
    summary = {
        "Backend flow status": [event["event_type"] for event in timeline["bundle"]["memory_replay"]["events"]],
        "Frontend render status": "surge_fixture_ready",
        "Avatar mapping status": ["patient", "triage_nurse", "doctor"],
        "Collision/path status": len(timeline["bundle"]["memory_replay"]["events"]),
        "Timeline export status": timeline["document"]["document_type"],
        "Memory/HIS consistency": timeline["bundle"]["contract_alignment"]["formal_patient_id"].startswith("P-"),
        "Conclusion": timeline["bundle"]["scenario_metadata"]["persona_names"],
    }
    print(summary)

    assert summary["Timeline export status"] == "timeline_export"
    assert "Patient 1" in summary["Conclusion"]
    assert summary["Memory/HIS consistency"] is True
