from tests_week8.support.fake_memory_service import InMemoryFakeService, NullMemoryService


def test_null_memory_service_is_fail_open():
    svc = NullMemoryService()
    assert svc.append_event(run_id="r", mode="user", encounter_id="e", patient_id="p", agent_role="x", event_type="y", content="z") is None
    assert svc.get_current_summary(run_id="r", mode="user", encounter_id="e") is None
    assert svc.retrieve(run_id="r", mode="user", encounter_id="e") == []


def test_inmemory_service_appends_monotonic_steps():
    svc = InMemoryFakeService()
    svc.append_event(run_id="r1", mode="user", encounter_id="e1", patient_id="p1", agent_role="PATIENT", event_type="encounter_started", content="start")
    svc.append_event(run_id="r1", mode="user", encounter_id="e1", patient_id="p1", agent_role="CALLING_NURSE", event_type="vitals_measured", content="v")
    events = svc.export_replay(run_id="r1", mode="user", encounter_id="e1")["events"]
    assert [e["step"] for e in events] == [1, 2]


def test_inmemory_retrieve_filters_event_types():
    svc = InMemoryFakeService()
    svc.append_event(run_id="r", mode="user", encounter_id="e", patient_id="p", agent_role="X", event_type="triage_completed", content="t")
    svc.append_event(run_id="r", mode="user", encounter_id="e", patient_id="p", agent_role="X", event_type="doctor_assessment_checkpoint", content="d")
    triage_only = svc.retrieve(run_id="r", mode="user", encounter_id="e", event_types=["triage_completed"], top_k=5)
    assert len(triage_only) == 1
    assert triage_only[0]["event_type"] == "triage_completed"
