from datetime import datetime, timezone
from types import SimpleNamespace

from auto_memory_hooks import AutoMemoryHookManager
from app_core.app.api_v1 import (
    complete_handoff,
    export_auto_timeline,
    export_encounter_timeline,
    request_handoff,
    reset_runtime_state,
    start_encounter,
)
from app_core.his.adapters.runtime_bridge import get_runtime_memory_service


def setup_function():
    reset_runtime_state()


def _new_user_encounter():
    return start_encounter(
        {
            "patient_id": "week9-ui-parity",
            "chief_complaint": "Chest pain with diaphoresis",
            "symptoms": ["shortness of breath", "radiating pain"],
            "vitals": {"spo2": 93, "sbp": 102},
        }
    )


def _make_auto_patient(name="Patient 3", state="WAITING_FOR_DOCTOR", zone="major injuries zone", ctas=2):
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


def test_user_mode_timeline_bundle_matches_memory_and_his_records():
    start_data = _new_user_encounter()
    requested = request_handoff(
        {
            "encounter_id": start_data["encounter_id"],
            "target_system": "ICU",
            "reason": "formal timeline parity",
        }
    )
    complete_handoff(
        {
            "handoff_ticket_id": requested["handoff_ticket_id"],
            "receiver_system": "ICU",
            "accepted": True,
            "receiver_bed": "ICU-08",
        }
    )

    timeline = export_encounter_timeline(start_data["encounter_id"])
    bundle = timeline["bundle"]
    replay = bundle["memory_replay"]

    replay_memory_ids = sorted(event["memory_id"] for event in replay["events"])
    his_memory_ids = sorted(entry["payload"]["memory_id"] for entry in bundle["event_registry"])

    assert replay_memory_ids == his_memory_ids
    assert replay["summaries"][-1]["current_state"] == bundle["summary"]["current_state"]
    assert len(replay["snapshots"]) == len(bundle["handoff_snapshots"])
    assert timeline["document"]["document_type"] == "timeline_export"
    assert timeline["registry"]["document_type"] == "timeline_export"
    assert timeline["audit"]["action"] == "timeline_export"


def test_auto_mode_timeline_export_hydrates_his_records_with_contract_mapping():
    frozen = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    manager = AutoMemoryHookManager(
        sim_code="curr_sim",
        start_time=frozen,
        service=get_runtime_memory_service(),
        now=frozen,
    )
    patient = _make_auto_patient()
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

    raw_encounter_id = f"auto_{manager.run_id}_Patient_3"
    timeline = export_auto_timeline(
        raw_encounter_id,
        run_id=manager.run_id,
        patient_id="Patient_3",
        patient_display_name="Patient 3",
        scenario_metadata={"scenario": "handoff_smoke"},
    )
    bundle = timeline["bundle"]
    replay = bundle["memory_replay"]
    alignment = bundle["contract_alignment"]

    assert bundle["patient"]["patient_id"] == alignment["formal_patient_id"]
    assert bundle["encounter"]["encounter_id"] == alignment["formal_encounter_id"]
    assert alignment["raw_encounter_id"] == raw_encounter_id
    assert len(bundle["event_registry"]) == len(replay["events"])
    assert len(bundle["handoff_snapshots"]) == len(replay["snapshots"])
    assert bundle["scenario_metadata"]["scenario"] == "handoff_smoke"
    assert timeline["document"]["document_type"] == "timeline_export"
    assert timeline["audit"]["action"] == "timeline_export"
