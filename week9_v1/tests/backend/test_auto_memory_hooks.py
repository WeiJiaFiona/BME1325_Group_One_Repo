from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from auto_memory_hooks import AutoMemoryHookManager
from app_core.memory.service import create_memory_service


def _make_patient(
    name: str = "Patient 3",
    *,
    state: str = "WAITING_FOR_DOCTOR",
    zone: str = "major injuries zone",
    ctas: int = 2,
) -> SimpleNamespace:
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


def _make_server(patient: SimpleNamespace) -> SimpleNamespace:
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


def test_auto_memory_hooks_record_encounter_started_and_summary(tmp_path):
    service = create_memory_service(root=tmp_path / "runtime_data" / "memory", enabled=True)
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=service,
        now=frozen,
    )
    patient = _make_patient()

    result = manager.record_encounter_started(
        patient,
        step=0,
        sim_time=frozen,
        source="seed_existing",
    )

    assert result["ok"] is True
    replay = service.export_replay(run_id=manager.run_id, mode="auto", encounter_id=f"auto_{manager.run_id}_Patient_3")
    assert len(replay["events"]) == 1
    assert replay["events"][0]["event_type"] == "encounter_started"
    assert len(replay["audits"]) >= 2
    summary = service.get_current_summary(manager.run_id, "auto", f"auto_{manager.run_id}_Patient_3")
    assert summary is not None
    assert summary.current_state == "WAITING_FOR_DOCTOR"
    assert summary.pending_tasks[0]["task"] == "triage_or_wait"


def test_auto_memory_hooks_boarding_timeout_is_deduplicated(tmp_path):
    service = create_memory_service(root=tmp_path / "runtime_data" / "memory", enabled=True)
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=service,
        now=frozen,
    )
    patient = _make_patient(state="ADMITTED_BOARDING")
    patient.scratch.boarding_timeout_at = frozen
    patient.scratch.admission_boarding_start = frozen
    manager.record_encounter_started(patient, step=0, sim_time=frozen, source="seed_existing")

    first = manager.record_boarding_timeout(patient, step=5, sim_time=frozen)
    second = manager.record_boarding_timeout(patient, step=5, sim_time=frozen)

    encounter_id = f"auto_{manager.run_id}_Patient_3"
    replay = service.export_replay(run_id=manager.run_id, mode="auto", encounter_id=encounter_id)
    event_types = [event["event_type"] for event in replay["events"]]

    assert first["ok"] is True
    assert second["skipped"] is True
    assert event_types.count("boarding_timeout") == 1


def test_auto_memory_hooks_resource_bottleneck_emits_once_per_active_condition(tmp_path):
    service = create_memory_service(root=tmp_path / "runtime_data" / "memory", enabled=True)
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=service,
        now=frozen,
    )
    patient = _make_patient()
    manager.record_encounter_started(patient, step=0, sim_time=frozen, source="seed_existing")
    server = _make_server(patient)

    first = manager.record_resource_bottlenecks(server, step=3, sim_time=frozen)
    second = manager.record_resource_bottlenecks(server, step=4, sim_time=frozen)
    encounter_id = f"auto_{manager.run_id}_Patient_3"
    replay = service.export_replay(run_id=manager.run_id, mode="auto", encounter_id=encounter_id)
    bottlenecks = [event for event in replay["events"] if event["event_type"] == "resource_bottleneck"]
    resources = sorted(event["structured_facts"]["resource"] for event in bottlenecks)

    assert len(first) == 2
    assert second == []
    assert resources == ["bedside_nurse_waiting", "doctor_global"]


def test_auto_memory_hooks_fail_open_on_write_error():
    class BrokenService:
        enabled = True

        def append_event(self, item):
            raise RuntimeError("boom")

        def update_current_summary(self, summary):
            raise AssertionError("should not update summary after failed append_event")

        def append_audit(self, record):
            return record

        def get_current_summary(self, run_id, mode, encounter_id):
            return None

    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=BrokenService(),
        now=frozen,
    )

    result = manager.record_encounter_started(
        _make_patient(),
        step=0,
        sim_time=frozen,
        source="seed_existing",
    )

    assert result["ok"] is False
    assert result["reason"] == "boom"


def test_auto_memory_hooks_disposition_and_next_slot_write_summary(tmp_path):
    service = create_memory_service(root=tmp_path / "runtime_data" / "memory", enabled=True)
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=service,
        now=frozen,
    )
    patient = _make_patient(state="WAITING_FOR_DOCTOR", zone="major injuries zone")
    patient.scratch.admitted_to_hospital = True
    patient.scratch.admission_boarding_start = frozen
    patient.scratch.admission_boarding_end = frozen

    disposition_result = manager.record_disposition_decided(
        patient,
        step=8,
        sim_time=frozen,
        disposition="admit",
    )
    next_slot_result = manager.record_next_slot(
        patient,
        step=8,
        sim_time=frozen,
        slot_name="boarding",
        owner_role="BedsideNurse",
        reason="patient_admitted_to_hospital",
    )

    encounter_id = f"auto_{manager.run_id}_Patient_3"
    replay = service.export_replay(run_id=manager.run_id, mode="auto", encounter_id=encounter_id)
    event_types = [event["event_type"] for event in replay["events"]]
    summary = service.get_current_summary(manager.run_id, "auto", encounter_id)

    assert disposition_result["ok"] is True
    assert next_slot_result["ok"] is True
    assert "disposition_decided" in event_types
    assert "next_slot" in event_types
    assert summary is not None
    assert summary.latest_doctor_findings["disposition"]["disposition"] == "admit"
    assert summary.latest_doctor_findings["next_slot"]["slot_name"] == "boarding"


def test_auto_memory_hooks_handoff_events_write_snapshots(tmp_path):
    service = create_memory_service(root=tmp_path / "runtime_data" / "memory", enabled=True)
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=service,
        now=frozen,
    )
    patient = _make_patient(state="WAITING_FOR_NURSE", zone="minor injuries zone")
    patient.scratch.next_room = "minor injuries zone"

    requested = manager.record_handoff_requested(
        patient,
        step=2,
        sim_time=frozen,
        from_role="TriageNurse",
        to_role="BedsideNurse",
        reason="transfer_to_minor_injuries_zone",
    )
    completed = manager.record_handoff_completed(
        patient,
        step=3,
        sim_time=frozen,
        from_role="TriageNurse",
        to_role="BedsideNurse",
        completion_note="patient_transferred_to_care_zone",
    )

    encounter_id = f"auto_{manager.run_id}_Patient_3"
    replay = service.export_replay(run_id=manager.run_id, mode="auto", encounter_id=encounter_id)
    event_types = [event["event_type"] for event in replay["events"]]
    snapshot_stages = sorted(snapshot["handoff_stage"] for snapshot in replay["snapshots"])

    assert requested["ok"] is True
    assert completed["ok"] is True
    assert "handoff_requested" in event_types
    assert "handoff_completed" in event_types
    assert snapshot_stages == ["completed", "requested"]
