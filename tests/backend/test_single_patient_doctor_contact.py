from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from persona.persona import Persona
from persona.persona_types.doctor import Doctor
from persona.persona_types.patient import Patient


class _FakeMaze:
    def __init__(self, *, bed_tile: tuple[int, int], bed_token=("bed-1",)):
        self.doctors_taking_more_patients = []
        self.patients_waiting_for_doctor = []
        self._bed_tile = bed_tile
        self._bed_token = tuple(bed_token)

    def assign_bed(self, patient_name, zone, current_assignment):
        if current_assignment:
            return tuple(current_assignment)
        return self._bed_token

    def get_bed_address(self, zone, bed):
        return self._bed_tile


def _fake_persona_move(self, maze, personas, curr_tile, curr_time, data_collection=None):
    self.scratch.curr_tile = curr_tile
    self.scratch.curr_time = curr_time
    self.scratch.act_address = f"<waiting> {curr_tile[0]} {curr_tile[1]}"
    return self.scratch.act_address


def _fake_execute(self, maze, personas, plan):
    return plan


def _doctor(name: str = "Doctor 1") -> Doctor:
    doctor = Doctor.__new__(Doctor)
    doctor.name = name
    doctor.role = "Doctor"
    doctor.runtime_step = 12
    doctor.scratch = SimpleNamespace(
        assigned_patients=[],
        assigned_patients_waitlist=[],
        next_step=None,
        time_to_next=None,
        chatting_with=None,
        chatting_patient=None,
        act_address=None,
        act_path_set=False,
        planned_path=[],
        curr_time=None,
        curr_tile=None,
        _tiles_per_step=1,
    )
    return doctor


def _patient(
    name: str = "Patient 1",
    *,
    curr_time: dt.datetime,
    bed_tile: tuple[int, int],
    zone: str = "major injuries zone",
) -> Patient:
    patient = Patient.__new__(Patient)
    patient.name = name
    patient.role = "Patient"
    patient.runtime_step = 12
    patient.testing_probability_by_ctas = {"1": 0.0}
    patient.scratch = SimpleNamespace(
        state="WAITING_FOR_FIRST_ASSESSMENT",
        CTAS=1,
        assigned_doctor="Doctor 1",
        initial_assessment_ready_at=curr_time - dt.timedelta(minutes=1),
        curr_time=curr_time,
        curr_tile=bed_tile,
        injuries_zone=zone,
        bed_assignment=["bed-1"],
        in_queue=True,
        act_path_set=False,
        initial_assessment_done=False,
        first_doctor_contact_minute=None,
        pending_conversation_events=[],
        active_conversation_event=None,
        last_conversation_event=None,
        last_conversation_step=None,
        stage2_minutes=0,
        stage2_surge_extra=0,
        disposition_ready_at=None,
        testing_kind=None,
        next_room=zone,
        next_step=f"ed map:emergency department:{zone}:bed",
        time_to_next=None,
        time_scale_minutes_per_step=1,
        user_controlled=False,
    )
    return patient


def test_single_patient_doctor_contact_records_first_contact(monkeypatch):
    curr_time = dt.datetime(2024, 1, 1, 9, 0, 0)
    bed_tile = (11, 2)
    maze = _FakeMaze(bed_tile=bed_tile)
    doctor = _doctor()
    patient = _patient(curr_time=curr_time, bed_tile=bed_tile)
    doctor.scratch.assigned_patients_waitlist = [[patient.scratch.CTAS * doctor.priority_factor, patient.name]]
    personas = {doctor.name: doctor, patient.name: patient}
    data_collection = {"Patients_Attended": []}

    monkeypatch.setattr(Persona, "move", _fake_persona_move, raising=True)
    monkeypatch.setattr(Doctor, "execute", _fake_execute, raising=True)
    monkeypatch.setattr(Patient, "execute", _fake_execute, raising=True)

    plan = doctor.move(
        maze,
        personas,
        curr_tile=(0, 0),
        curr_time=curr_time,
        data_collection=data_collection,
    )

    assert patient.scratch.assigned_doctor == doctor.name, "assigned_doctor missing"
    assert patient.scratch.initial_assessment_ready_at <= curr_time, "ready_at not reached"
    assert patient.scratch.curr_tile == maze.get_bed_address(patient.scratch.injuries_zone, patient.scratch.bed_assignment), "exact bed tile mismatch"
    assert patient.scratch.initial_assessment_done is True, "do_initial_assessment not called"
    assert patient.scratch.first_doctor_contact_minute == 12, "first_doctor_contact not recorded"
    assert patient.scratch.state == "WAITING_FOR_RESULT"
    assert doctor.scratch.assigned_patients_waitlist == []
    assert any(
        event.get("patient") == patient.name and event.get("doctor") == doctor.name
        for event in data_collection.get("Doctor_Assignment_Events", [])
    )
    assert plan == f"<persona> {patient.name}"
