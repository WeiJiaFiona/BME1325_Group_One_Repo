import datetime
from types import SimpleNamespace

from persona.persona_types.doctor import Doctor
from persona.persona_types.patient import Patient
from persona.persona_types.triage_nurse import Triage_Nurse


def build_patient(*, state="WAITING_FOR_TRIAGE", curr_time=None):
    patient = Patient.__new__(Patient)
    patient.name = "Patient 1"
    patient.role = "Patient"
    patient.testing_probability_by_ctas = {"3": 0.5}
    patient.testing_kind_for_ctas = None
    patient.simulate_hospital_admission = False
    patient.admission_probability_by_ctas = {}
    patient.post_discharge_linger_probability = 0.0
    patient.scratch = SimpleNamespace(
        state=state,
        next_step=None,
        next_room=None,
        injuries_zone="major injuries zone",
        curr_time=curr_time or datetime.datetime(2024, 1, 1, 9, 0, 0),
        pending_conversation_events=[],
        active_conversation_event=None,
        last_conversation_event=None,
        last_conversation_step=None,
        conversation_cooldown_steps=2,
        last_handoff_step=None,
        last_result_notified_at=None,
        act_path_set=False,
        initial_assessment_done=False,
        stage2_minutes=0,
        disposition_ready_at=None,
        CTAS=3,
        testing_kind=None,
        time_to_next=None,
        stage2_surge_extra=0,
        disposition_done=False,
        assigned_doctor=None,
        exit_ready_at=None,
        stage3_minutes=0,
        admitted_to_hospital=False,
        admission_boarding_start=None,
        boarding_timeout_recorded=False,
        boarding_timeout_at=None,
    )
    return patient


def build_triage_nurse():
    nurse = Triage_Nurse.__new__(Triage_Nurse)
    nurse.scratch = SimpleNamespace()
    return nurse


def build_doctor(next_step):
    doctor = Doctor.__new__(Doctor)
    doctor.scratch = SimpleNamespace(next_step=next_step)
    return doctor


def test_to_triage_queues_first_contact_event():
    patient = build_patient()

    patient.to_triage(SimpleNamespace(name="Triage Nurse 1"))

    assert patient.scratch.state == "TRIAGE"
    assert Patient.EVENT_TRIAGE_FIRST_CONTACT in patient.scratch.pending_conversation_events


def test_do_initial_assessment_queues_test_ordered_when_testing_selected(monkeypatch):
    patient = build_patient(state="WAITING_FOR_FIRST_ASSESSMENT")
    monkeypatch.setattr("persona.persona_types.patient.random.random", lambda: 0.0)

    applied = patient.do_initial_assessment(SimpleNamespace(name="Doctor 1"), SimpleNamespace())

    assert applied is True
    assert patient.scratch.state == "WAITING_FOR_TEST"
    assert Patient.EVENT_DOCTOR_FIRST_ASSESS in patient.scratch.pending_conversation_events
    assert Patient.EVENT_TEST_ORDERED in patient.scratch.pending_conversation_events


def test_triage_nurse_chat_is_event_gated_and_respects_cooldown():
    patient = build_patient(state="TRIAGE")
    triage_nurse = build_triage_nurse()

    assert triage_nurse.decide_to_chat(patient) is False

    patient.queue_conversation_event(Patient.EVENT_TRIAGE_FIRST_CONTACT)
    assert triage_nurse.decide_to_chat(patient) is True
    assert patient.scratch.active_conversation_event == Patient.EVENT_TRIAGE_FIRST_CONTACT

    patient.consume_active_conversation_event()
    patient.queue_conversation_event(Patient.EVENT_TRIAGE_FIRST_CONTACT)

    assert triage_nurse.decide_to_chat(patient) is False


def test_doctor_chat_requires_pending_patient_event():
    patient = build_patient(state="WAITING_FOR_RESULT")
    doctor = build_doctor("<persona> Patient 1")

    assert doctor.decide_to_chat(patient) is False

    patient.queue_conversation_event(Patient.EVENT_TEST_RESULT_READY)
    doctor.scratch.next_step = "<persona> Patient 1"

    assert doctor.decide_to_chat(patient) is True
    assert patient.scratch.active_conversation_event == Patient.EVENT_TEST_RESULT_READY
