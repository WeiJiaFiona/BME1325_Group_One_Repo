from app_core.app.mode_user import start
from app_core.app.handoff import request, complete


def test_missing_chief_complaint():
    resp = start({"vitals": {"spo2": 95, "sbp": 120}})
    assert resp["error_code"] == "MISSING_FIELD"


def test_invalid_vitals_type():
    resp = start({"chief_complaint": "fever", "vitals": {"spo2": "low", "sbp": 120}})
    assert resp["error_code"] == "INVALID_TYPE"


def test_missing_spo2():
    resp = start({"chief_complaint": "fever", "vitals": {"sbp": 120}})
    assert resp["error_code"] == "MISSING_FIELD"


def test_invalid_arrival_mode():
    resp = start({"chief_complaint": "fever", "vitals": {"spo2": 95, "sbp": 120}, "arrival_mode": "taxi"})
    assert resp["error_code"] == "INVALID_TYPE"


def test_handoff_request_missing_patient():
    resp = request({
        "acuity_ad": "A",
        "zone": "red",
        "stability": "critical",
        "required_unit": "ICU",
        "clinical_summary": "summary",
        "pending_tasks": [],
    })
    assert resp["error_code"] == "MISSING_FIELD"


def test_handoff_complete_missing_ticket():
    resp = complete({"receiver_system": "ICU", "accepted_at": "2026-04-08T00:00:00Z", "receiver_bed": "ICU-1"})
    assert resp["error_code"] == "MISSING_FIELD"
