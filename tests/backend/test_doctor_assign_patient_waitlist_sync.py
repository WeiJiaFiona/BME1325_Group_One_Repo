from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from persona.persona_types.doctor import Doctor


def _doctor(name: str = "Doctor 1") -> Doctor:
    doctor = Doctor.__new__(Doctor)
    doctor.name = name
    doctor.priority_factor = 3
    doctor.max_patients = 5
    doctor.TERMINAL_STATES = frozenset({"LEAVING"})
    doctor.scratch = SimpleNamespace(
        assigned_patients=[],
        assigned_patients_waitlist=[],
    )
    return doctor


def _patient(
    name: str,
    *,
    ctas: int,
    arrival_minute: float,
    triage_completed_minute: float,
    first_doctor_contact_minute=None,
):
    patient = SimpleNamespace()
    patient.name = name
    patient.scratch = SimpleNamespace(
        CTAS=ctas,
        ed_arrival_minute=arrival_minute,
        triage_completed_minute=triage_completed_minute,
        first_doctor_contact_minute=first_doctor_contact_minute,
        assigned_doctor=None,
        state="WAITING_FOR_FIRST_ASSESSMENT",
    )
    return patient


def test_assign_patient_syncs_waitlist_and_assigned_doctor():
    doctor = _doctor()
    patient = _patient("Patient 1", ctas=2, arrival_minute=10, triage_completed_minute=12)
    queue = [doctor.name]
    personas = {patient.name: patient}

    doctor.assign_patient(queue, patient, personas)

    assert patient.scratch.assigned_doctor == doctor.name
    assert doctor.scratch.assigned_patients == [patient.name]
    assert doctor.scratch.assigned_patients_waitlist == [[patient.scratch.CTAS * doctor.priority_factor, patient.name]]


def test_assign_patient_does_not_duplicate_waitlist_entry():
    doctor = _doctor()
    patient = _patient("Patient 1", ctas=2, arrival_minute=10, triage_completed_minute=12)
    queue = [doctor.name]
    personas = {patient.name: patient}

    doctor.assign_patient(queue, patient, personas)
    doctor.assign_patient(queue, patient, personas)

    assert doctor.scratch.assigned_patients == [patient.name]
    assert doctor.scratch.assigned_patients_waitlist == [[patient.scratch.CTAS * doctor.priority_factor, patient.name]]


def test_assign_patient_skips_waitlist_if_contact_already_recorded():
    doctor = _doctor()
    patient = _patient(
        "Patient 1",
        ctas=1,
        arrival_minute=3,
        triage_completed_minute=5,
        first_doctor_contact_minute=17,
    )
    queue = [doctor.name]
    personas = {patient.name: patient}

    doctor.assign_patient(queue, patient, personas)

    assert patient.scratch.assigned_doctor == doctor.name
    assert doctor.scratch.assigned_patients == [patient.name]
    assert doctor.scratch.assigned_patients_waitlist == []


def test_assign_patient_waitlist_uses_ctas_priority_key_order():
    doctor = _doctor()
    p3 = _patient("Patient 3", ctas=3, arrival_minute=5, triage_completed_minute=7)
    p1 = _patient("Patient 1", ctas=1, arrival_minute=20, triage_completed_minute=21)
    p2_early = _patient("Patient 2", ctas=2, arrival_minute=4, triage_completed_minute=8)
    p2_late = _patient("Patient 4", ctas=2, arrival_minute=9, triage_completed_minute=10)
    queue = [doctor.name]
    personas = {p.name: p for p in [p3, p1, p2_early, p2_late]}

    doctor.assign_patient(queue, p3, personas)
    doctor.assign_patient(queue, p2_late, personas)
    doctor.assign_patient(queue, p1, personas)
    doctor.assign_patient(queue, p2_early, personas)

    assert [entry[1] for entry in doctor.scratch.assigned_patients_waitlist] == [
        "Patient 1",
        "Patient 2",
        "Patient 4",
        "Patient 3",
    ]
