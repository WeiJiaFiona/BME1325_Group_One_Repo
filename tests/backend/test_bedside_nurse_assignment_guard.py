from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from bedside_queue_guards import select_bedside_patient_for_assignment


def _patient(name: str, next_room: str = "major injuries zone"):
    return SimpleNamespace(
        name=name,
        scratch=SimpleNamespace(
            next_room=next_room,
            state="WAITING_FOR_NURSE",
        ),
    )


def test_same_step_assignment_guard_prevents_duplicate_patient_assignment():
    queue = [[1, "Patient 1"], [2, "Patient 2"]]
    personas = {"Patient 1": _patient("Patient 1"), "Patient 2": _patient("Patient 2")}
    assigned = set()

    first, first_entry, _ = select_bedside_patient_for_assignment(
        queue=queue,
        personas=personas,
        zone_has_space=lambda zone: True,
        reserve_bed=lambda patient, zone: None,
        assigned_patient_ids_this_step=assigned,
    )
    second, second_entry, _ = select_bedside_patient_for_assignment(
        queue=queue,
        personas=personas,
        zone_has_space=lambda zone: True,
        reserve_bed=lambda patient, zone: None,
        assigned_patient_ids_this_step=assigned,
    )

    assert first.name == "Patient 1"
    assert first_entry[1] == "Patient 1"
    assert second.name == "Patient 2"
    assert second_entry[1] == "Patient 2"
    assert assigned == {"Patient 1", "Patient 2"}


def test_already_assigned_patient_is_skipped_even_if_still_in_queue():
    queue = [[1, "Patient 1"], [2, "Patient 2"]]
    personas = {"Patient 1": _patient("Patient 1"), "Patient 2": _patient("Patient 2")}
    assigned = {"Patient 1"}

    selected, entry, _ = select_bedside_patient_for_assignment(
        queue=queue,
        personas=personas,
        zone_has_space=lambda zone: True,
        reserve_bed=lambda patient, zone: None,
        assigned_patient_ids_this_step=assigned,
    )

    assert selected.name == "Patient 2"
    assert entry[1] == "Patient 2"
    assert "Patient 1" in [item[1] for item in queue]
