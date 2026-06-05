from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from downstream_units.transfer_broker import TransferBroker


def _broker(tmp_path: Path, *, icu_capacity: int = 1, ward_capacity: int = 2) -> TransferBroker:
    return TransferBroker(
        profile_name="unit_test_profile",
        icu_capacity=icu_capacity,
        ward_capacity=ward_capacity,
        transfer_turnaround_minutes=30,
        boarding_timeout_minutes=120,
        minutes_per_step=1,
        request_log_path=tmp_path / "transfer_requests.jsonl",
    )


def test_transfer_broker_returns_accepted_when_bed_exists(tmp_path: Path):
    broker = _broker(tmp_path, icu_capacity=1)
    response = broker.request_transfer(
        encounter_id="enc_001",
        patient_id="patient_001",
        from_group="ED",
        to_group="ICU",
        from_unit="ED",
        to_unit="ICU",
        request_step=10,
        request_minute=10,
        ctas_level=1,
        reason="critical_care_needed",
        summary="ICU admit",
    )
    assert response.status == "accepted"
    assert response.accepted is True
    assert response.assigned_bed == "ICU-BED-001"
    assert response.transfer_completed_minute == 40
    assert broker.runtime_summary()["accepted_transfer_count"] == 1


def test_transfer_broker_returns_pending_for_bed_shortage_not_terminal_rejected(tmp_path: Path):
    broker = _broker(tmp_path, icu_capacity=0)
    response = broker.request_transfer(
        encounter_id="enc_001",
        patient_id="patient_001",
        from_group="ED",
        to_group="ICU",
        from_unit="ED",
        to_unit="ICU",
        request_step=10,
        request_minute=10,
        ctas_level=1,
        reason="critical_care_needed",
        summary="ICU admit",
    )
    assert response.status == "pending"
    assert response.accepted is False
    assert response.reason == "icu_bed_unavailable"
    assert response.next_check_minute is not None
    assert broker.runtime_summary()["pending_transfer_count"] == 1
    log_lines = (tmp_path / "transfer_requests.jsonl").read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(log_lines[0])
    assert payload["response"]["status"] == "pending"
