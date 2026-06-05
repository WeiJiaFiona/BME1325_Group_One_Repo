from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from downstream_units.disposition_target_resolver import DispositionTargetResolver
from downstream_units.transfer_broker import TransferBroker
from failure_metrics import collect_failure_metrics
from persona.persona_types.patient import Patient
from success_metrics import compute_throughput_success_metrics


class FakeDoctor:
    name = "Doctor 1"

    def remove_patient(self, patient, maze):
        return None


class FakeMaze:
    def __init__(self):
        self.tiles = [[{"arena": "minor injuries zone"}]]
        self.triage_queue = []
        self.patients_waiting_for_doctor = []
        self.lab_patients = []
        self.imaging_patients = []
        self.doctors_taking_more_patients = []
        self.injuries_zones = {
            "diagnostic room": {"current_patients": []},
            "bedside_nurse_waiting": [],
            "pager": [],
            "assessment_queue": [],
            "minor injuries zone": {"current_patients": [], "capacity": 10},
        }

    def discharge_patient(self, patient_name, zone):
        return None

    def assign_bed(self, patient_name, zone, existing):
        return (0, 0)

    def get_bed_address(self, zone, bed):
        return f"ed map:emergency department:{zone}:bed"


def _build_patient(tmp_path: Path, *, icu_capacity: int) -> Patient:
    patient_dir = tmp_path / "personas" / "Patient 1"
    bootstrap_dir = patient_dir / "bootstrap_memory"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    scratch_path = bootstrap_dir / "scratch.json"
    patient = Patient("Patient 1", folder_mem_saved=str(patient_dir), role="Patient", ICD="A00", seed=42)
    patient.scratch.state = "WAITING_FOR_DOCTOR"
    patient.scratch.curr_time = dt.datetime(2026, 1, 1, 8, 0, 0)
    patient.scratch.injuries_zone = "minor injuries zone"
    patient.scratch.CTAS = 1
    patient.runtime_step = 10
    patient.simulate_hospital_admission = True
    patient.admission_probability_by_ctas = {"1": 1.0}
    patient.boarding_timeout_minutes = 120
    patient.execute = lambda maze, personas, plan: plan
    Patient.transfer_broker = TransferBroker(
        profile_name="unit_test_profile",
        icu_capacity=icu_capacity,
        ward_capacity=1,
        transfer_turnaround_minutes=30,
        boarding_timeout_minutes=120,
        minutes_per_step=1,
        request_log_path=tmp_path / "transfer_requests.jsonl",
    )
    Patient.disposition_target_resolver = DispositionTargetResolver({"1": {"ICU": 1.0}})
    return patient


def test_pending_transfer_records_boarding_and_timeout(tmp_path: Path):
    patient = _build_patient(tmp_path, icu_capacity=0)
    patient.do_disposition(FakeDoctor(), FakeMaze())
    assert patient.scratch.transfer_status == "pending"
    assert patient.scratch.boarding_started_minute == 10
    patient.scratch.curr_time = dt.datetime(2026, 1, 1, 10, 1, 0)
    patient.runtime_step = 121
    data_collection = patient.data_collection_dict()
    patient.move(FakeMaze(), {}, (0, 0), patient.scratch.curr_time, data_collection)
    assert patient.scratch.boarding_timeout_recorded is True
    assert patient.scratch.boarding_timeout_minute == 121
    failure = collect_failure_metrics(
        personas={"Patient 1": patient},
        maze=None,
        data_collection={"Patient": {"Patient 1": patient.save_data(patient.data_collection_dict())}},
        meta={},
        curr_time=patient.scratch.curr_time,
        curr_step=patient.runtime_step,
    )
    assert failure["failure_reason_counts"]["boarding_timeout"] == 1


def test_accepted_transfer_produces_ed_exit_evidence_and_throughput(tmp_path: Path):
    patient = _build_patient(tmp_path, icu_capacity=1)
    maze = FakeMaze()
    patient.do_disposition(FakeDoctor(), maze)
    assert patient.scratch.transfer_status == "accepted"
    patient.runtime_step = int(patient.scratch.transfer_completed_step)
    patient.scratch.curr_time = dt.datetime(2026, 1, 1, 8, 30, 0)
    data_collection = patient.data_collection_dict()
    patient.move(maze, {}, (0, 0), patient.scratch.curr_time, data_collection)
    patient.leave_ed(maze, {}, str(tmp_path), data_collection=data_collection)
    saved = patient.save_data(patient.data_collection_dict())
    assert saved["ed_exit_minute"] is not None
    assert saved["icu_admit_minute"] == 40
    throughput = compute_throughput_success_metrics(
        patient_records={"Patient 1": saved},
        total_arrived_patients=1,
        physical_window_minutes=300,
    )
    assert throughput["throughput_success_rate"] == 1.0
