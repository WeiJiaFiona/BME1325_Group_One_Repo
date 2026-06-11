from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bedside_queue_guards import guarded_bedside_reinsert


def _patient(name: str = "Patient 1", arrival=0, triage=5):
    return SimpleNamespace(
        name=name,
        scratch=SimpleNamespace(
            ed_arrival_minute=arrival,
            triage_completed_minute=triage,
            bedside_reinsert_count=0,
        ),
    )


def test_same_patient_already_in_bedside_queue_not_reinserted():
    queue = [[3, "Patient 1"]]
    inserted, reason = guarded_bedside_reinsert(
        queue=queue,
        patient=_patient(),
        priority=3,
        data_collection={"Patient": {"Patient 1": {}}},
    )
    assert inserted is False
    assert reason == "already_in_bedside_nurse_waiting"
    assert queue == [[3, "Patient 1"]]


def test_missing_evidence_patient_not_reinserted():
    queue = []
    patient = _patient(arrival=None, triage=None)
    inserted, reason = guarded_bedside_reinsert(
        queue=queue,
        patient=patient,
        priority=3,
        data_collection={"Patient": {"Patient 1": {}}},
    )
    assert inserted is False
    assert reason == "missing_arrival_or_triage_evidence"
    assert queue == []
    assert patient.scratch.bedside_reinsert_count == 0


def test_reinsert_count_over_three_warns_and_suppresses_repeat_insert():
    queue = []
    patient = _patient()
    patient.scratch.bedside_reinsert_count = 3
    inserted, reason = guarded_bedside_reinsert(
        queue=queue,
        patient=patient,
        priority=3,
        data_collection={"Patient": {"Patient 1": {}}},
    )
    assert inserted is False
    assert reason == "reinsert_count_exceeded_warning"
    assert queue == []
    assert patient.scratch.bedside_reinsert_count == 4
