import pytest

from week5_system.app.mode_user import start


@pytest.mark.parametrize(
    "payload",
    [
        {
            "chief_complaint": "Chest pain with cold sweat",
            "symptoms": ["diaphoresis"],
            "vitals": {"spo2": 95, "sbp": 120},
            "arrival_mode": "walk-in",
        },
        {
            "chief_complaint": "Ambulance trauma",
            "symptoms": ["trauma"],
            "vitals": {"spo2": 92, "sbp": 110},
            "arrival_mode": "ambulance",
        },
        {
            "chief_complaint": "Dyspnea and fever",
            "symptoms": ["fever", "dyspnea"],
            "vitals": {"spo2": 88, "sbp": 118},
            "arrival_mode": "walk-in",
        },
    ],
)
def test_mode_user_contract(payload):
    resp = start(payload)
    assert "error_code" not in resp
    assert "patient_id" in resp
    assert "triage" in resp
    assert "final_state" in resp
    assert "state_trace" in resp
    assert "event_trace" in resp
    assert isinstance(resp["event_trace"], list)
    assert any(evt["event"] == "triage_completed" for evt in resp["event_trace"])
    assert any(evt["event"] == "encounter_completed" for evt in resp["event_trace"])
