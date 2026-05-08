from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Dict, List, Optional, Tuple

from app_core.app.mode_user import start as run_user_encounter


@dataclass(frozen=True)
class StaffingConfig:
    doctors: int
    triage_nurses: int
    bedside_nurses: int


@dataclass
class WorkerTask:
    patient_id: str
    remaining_steps: int


@dataclass(frozen=True)
class SurgeSimulationResult:
    total_patients: int
    completed_patients: int
    final_step: int
    timed_out: bool
    max_triage_queue: int
    max_nurse_queue: int
    max_doctor_queue: int
    high_acuity_completed: int
    low_acuity_completed: int


def _service_time_for_nurse(level: int) -> int:
    if level <= 1:
        return 1
    if level == 2:
        return 2
    if level == 3:
        return 2
    return 0


def _service_time_for_doctor(level: int) -> int:
    if level <= 1:
        return 4
    if level == 2:
        return 3
    if level == 3:
        return 2
    return 1


def _default_surge_payloads(num_patients: int) -> List[Dict[str, object]]:
    templates: List[Dict[str, object]] = [
        {
            "chief_complaint": "Chest pain with cold sweat",
            "symptoms": ["diaphoresis", "shortness of breath"],
            "vitals": {"spo2": 95, "sbp": 120},
        },
        {
            "chief_complaint": "FAST positive with slurred speech",
            "symptoms": ["stroke signs"],
            "vitals": {"spo2": 96, "sbp": 138},
        },
        {
            "chief_complaint": "fever and dizziness",
            "symptoms": ["fatigue"],
            "vitals": {"spo2": 86, "sbp": 110},
        },
        {
            "chief_complaint": "abdominal pain",
            "symptoms": ["needs blood test", "needs CT"],
            "vitals": {"spo2": 98, "sbp": 122},
        },
        {
            "chief_complaint": "mild ankle sprain",
            "symptoms": ["mild sprain"],
            "vitals": {"spo2": 99, "sbp": 124},
        },
    ]

    payloads: List[Dict[str, object]] = []
    for i in range(num_patients):
        item = dict(templates[i % len(templates)])
        item["patient_id"] = f"surge-patient-{i+1}"
        payloads.append(item)
    return payloads


def run_multi_agent_surge(
    staffing: StaffingConfig,
    num_patients: int = 20,
    max_steps: int = 500,
) -> SurgeSimulationResult:
    """
    Discrete-time queue simulation for Week5 interaction stress test.

    Flow:
    ARRIVAL -> TRIAGE_QUEUE -> (NURSE_QUEUE optional) -> DOCTOR_QUEUE -> COMPLETE
    """
    payloads = _default_surge_payloads(num_patients)

    triage_decisions: Dict[str, Dict[str, object]] = {}
    arrival_order: Dict[str, int] = {}
    for idx, payload in enumerate(payloads):
        pid = str(payload["patient_id"])
        triage_decisions[pid] = run_user_encounter(payload)["triage"]
        arrival_order[pid] = idx

    triage_queue: List[str] = [str(p["patient_id"]) for p in payloads]
    nurse_queue: List[Tuple[int, int, str]] = []
    doctor_queue: List[Tuple[int, int, str]] = []

    triage_workers: List[Optional[WorkerTask]] = [None] * staffing.triage_nurses
    nurse_workers: List[Optional[WorkerTask]] = [None] * staffing.bedside_nurses
    doctor_workers: List[Optional[WorkerTask]] = [None] * staffing.doctors

    completed: List[str] = []

    max_triage_queue = len(triage_queue)
    max_nurse_queue = 0
    max_doctor_queue = 0

    def _advance_workers(
        workers: List[Optional[WorkerTask]],
        on_complete,
    ) -> bool:
        progressed = False
        for i, task in enumerate(workers):
            if task is None:
                continue
            task.remaining_steps -= 1
            progressed = True
            if task.remaining_steps <= 0:
                pid = task.patient_id
                workers[i] = None
                on_complete(pid)
                progressed = True
        return progressed

    def _on_triage_complete(pid: str) -> None:
        triage = triage_decisions[pid]
        level = int(triage["level_1_4"])
        if level == 4:
            heapq.heappush(doctor_queue, (level, arrival_order[pid], pid))
        else:
            heapq.heappush(nurse_queue, (level, arrival_order[pid], pid))

    def _on_nurse_complete(pid: str) -> None:
        triage = triage_decisions[pid]
        level = int(triage["level_1_4"])
        heapq.heappush(doctor_queue, (level, arrival_order[pid], pid))

    def _on_doctor_complete(pid: str) -> None:
        completed.append(pid)

    final_step = 0
    timed_out = True

    for step in range(1, max_steps + 1):
        final_step = step
        progressed = False

        progressed |= _advance_workers(triage_workers, _on_triage_complete)
        progressed |= _advance_workers(nurse_workers, _on_nurse_complete)
        progressed |= _advance_workers(doctor_workers, _on_doctor_complete)

        for i in range(len(triage_workers)):
            if triage_workers[i] is None and triage_queue:
                pid = triage_queue.pop(0)
                triage_workers[i] = WorkerTask(patient_id=pid, remaining_steps=1)
                progressed = True

        for i in range(len(nurse_workers)):
            if nurse_workers[i] is None and nurse_queue:
                level, _, pid = heapq.heappop(nurse_queue)
                nurse_workers[i] = WorkerTask(patient_id=pid, remaining_steps=_service_time_for_nurse(level))
                progressed = True

        for i in range(len(doctor_workers)):
            if doctor_workers[i] is None and doctor_queue:
                level, _, pid = heapq.heappop(doctor_queue)
                doctor_workers[i] = WorkerTask(patient_id=pid, remaining_steps=_service_time_for_doctor(level))
                progressed = True

        max_triage_queue = max(max_triage_queue, len(triage_queue))
        max_nurse_queue = max(max_nurse_queue, len(nurse_queue))
        max_doctor_queue = max(max_doctor_queue, len(doctor_queue))

        if len(completed) == num_patients:
            timed_out = False
            break

        # deadlock guard: if nothing progressed and unfinished workload remains
        if (
            not progressed
            and (triage_queue or nurse_queue or doctor_queue or any(triage_workers) or any(nurse_workers) or any(doctor_workers))
        ):
            timed_out = True
            break

    high_acuity_completed = 0
    low_acuity_completed = 0
    for pid in completed:
        level = int(triage_decisions[pid]["level_1_4"])
        if level <= 2:
            high_acuity_completed += 1
        if level == 4:
            low_acuity_completed += 1

    return SurgeSimulationResult(
        total_patients=num_patients,
        completed_patients=len(completed),
        final_step=final_step,
        timed_out=timed_out,
        max_triage_queue=max_triage_queue,
        max_nurse_queue=max_nurse_queue,
        max_doctor_queue=max_doctor_queue,
        high_acuity_completed=high_acuity_completed,
        low_acuity_completed=low_acuity_completed,
    )
