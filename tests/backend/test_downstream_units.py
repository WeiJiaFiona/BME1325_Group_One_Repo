from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from downstream_units.icu_unit import ICUUnit
from downstream_units.ward_unit import WardUnit


def test_icu_unit_accept_release_capacity():
    unit = ICUUnit(capacity=1)
    bed_id = unit.accept("patient_001")
    assert bed_id == "ICU-BED-001"
    assert unit.current_occupancy == 1
    assert unit.available_capacity == 0
    assert unit.can_accept() is False
    assert unit.release("patient_001") is True
    assert unit.current_occupancy == 0
    assert unit.available_capacity == 1


def test_ward_unit_capacity_zero_never_accepts():
    unit = WardUnit(capacity=0)
    assert unit.can_accept() is False
    assert unit.accept("patient_001") is None
    assert unit.current_occupancy == 0
