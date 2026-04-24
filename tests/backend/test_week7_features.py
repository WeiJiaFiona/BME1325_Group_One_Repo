import datetime
from types import SimpleNamespace

from persona.persona_types.patient import Patient
from week7_logic import (
    arrival_profile_multiplier,
    boarding_timeout_reached,
    effective_arrival_rate,
    testing_kind_for_ctas as week7_testing_kind_for_ctas,
)


class DummyDoctor:
    def __init__(self):
        self.scratch = SimpleNamespace(assigned_patients_waitlist=[])


class DummyMaze:
    def __init__(self):
        self.tiles = [[{"arena": "waiting room"} for _ in range(5)] for _ in range(5)]
        self.lab_patients = []
        self.imaging_patients = []
        self.lab_capacity = 1
        self.imaging_capacity = 1
        self.patients_waiting_for_doctor = []
        self.injuries_zones = {
            "diagnostic room": {"current_patients": [], "capacity": 1},
            "bedside_nurse_waiting": [],
        }

    def assign_bed(self, patient_name, zone, existing_assignment):
        return tuple(existing_assignment) if existing_assignment else (2, 3)

    def get_bed_address(self, zone, bed):
        return tuple(bed)

    def discharge_patient(self, patient_name, injuries_zone):
        return None


def build_patient(*, state, assigned_doctor="Doctor 1", ctas=3, testing_kind=None):
    patient = Patient.__new__(Patient)
    patient.name = "Patient 1"
    patient.priority_factor = 3
    patient.lab_turnaround_minutes = 15
    patient.imaging_turnaround_minutes = 40
    patient.boarding_timeout_minutes = 120
    patient.execute = lambda maze, personas, plan: plan
    patient.scratch = SimpleNamespace(
        state=state,
        testing_kind=testing_kind,
        chatting_end_time=None,
        chatting_with=None,
        chat=None,
        act_path_set=True,
        assigned_doctor=assigned_doctor,
        time_to_next=None,
        CTAS=ctas,
        in_queue=False,
        injuries_zone="major injuries zone",
        bed_assignment=[2, 3],
        next_step=None,
        next_room=None,
        curr_time=None,
        curr_tile=None,
        act_address=None,
        disposition_ready_at=None,
        stage2_surge_extra=0,
        testing_end_time=None,
        admission_boarding_start=None,
        boarding_timeout_recorded=False,
        boarding_timeout_at=None,
        initial_assessment_ready_at=None,
        lingering_after_discharge=False,
        linger_recorded=False,
        linger_started_at=None,
        linger_duration_minutes=None,
        linger_end_time=None,
        left_without_being_seen=False,
        walkout_last_check_minute=0.0,
        act_pronunciatio=None,
        exit_ready_at=None,
        admission_boarding_end=None,
        planned_path=[],
    )
    return patient


def build_data_collection():
    return {
        "time_spent_area": {},
        "time_spent_state": {},
    }


class TestArrivalProfiles:
    def test_surge_multiplier_exceeds_normal(self):
        assert arrival_profile_multiplier("surge", 8) > arrival_profile_multiplier("normal", 8)

    def test_burst_peaks_during_configured_hours(self):
        assert arrival_profile_multiplier("burst", 17) > arrival_profile_multiplier("burst", 3)

    def test_effective_arrival_rate_never_negative(self):
        assert effective_arrival_rate(-5, "burst", 8) == 0.0


class TestTestingFlows:
    def test_ctas_routes_to_imaging_for_high_acuity(self):
        assert week7_testing_kind_for_ctas(2) == "imaging"

    def test_ctas_routes_to_lab_for_lower_acuity(self):
        assert week7_testing_kind_for_ctas(4) == "lab"

    def test_lab_capacity_starts_turnaround_when_slot_available(self):
        maze = DummyMaze()
        personas = {"Doctor 1": DummyDoctor()}
        patient = build_patient(state="WAITING_FOR_TEST", ctas=4)
        now = datetime.datetime(2024, 1, 1, 9, 0, 0)
        data_collection = build_data_collection()

        patient.move(maze, personas, (1, 1), now, data_collection)

        assert patient.scratch.state == "WAITING_FOR_RESULT"
        assert patient.name in maze.lab_patients
        assert patient.scratch.testing_end_time == now + datetime.timedelta(minutes=15)
        assert data_collection["testing_kind"] == "lab"

    def test_imaging_capacity_starts_turnaround_when_room_available(self):
        maze = DummyMaze()
        personas = {"Doctor 1": DummyDoctor()}
        patient = build_patient(state="WAITING_FOR_TEST", ctas=2)
        now = datetime.datetime(2024, 1, 1, 9, 0, 0)
        data_collection = build_data_collection()

        patient.move(maze, personas, (1, 1), now, data_collection)

        assert patient.scratch.state == "GOING_FOR_TEST"
        assert patient.name in maze.imaging_patients
        assert patient.name in maze.injuries_zones["diagnostic room"]["current_patients"]
        assert patient.scratch.testing_end_time == now + datetime.timedelta(minutes=40)
        assert data_collection["testing_kind"] == "imaging"


class TestBoardingTimeouts:
    def test_timeout_helper_triggers_at_threshold(self):
        start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        current = start + datetime.timedelta(minutes=120)
        assert boarding_timeout_reached(start, current, 120)

    def test_patient_records_boarding_timeout_event(self):
        maze = DummyMaze()
        personas = {}
        patient = build_patient(state="ADMITTED_BOARDING", assigned_doctor=None)
        start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        now = start + datetime.timedelta(minutes=121)
        patient.scratch.admission_boarding_start = start
        data_collection = build_data_collection()

        patient.move(maze, personas, (1, 1), now, data_collection)

        assert patient.scratch.boarding_timeout_recorded is True
        assert data_collection["boarding_timeout_event"]["occurred"] is True
        assert data_collection["boarding_timeout_event"]["threshold_minutes"] == 120.0
