from app_core.app.mode_user import start
from app_core.rule_core.state_machine import EncounterStateMachine


def test_chest_pain_diaphoresis():
    payload = {
        "patient_id": "p1",
        "chief_complaint": "Chest pain with cold sweat",
        "symptoms": ["diaphoresis", "shortness of breath"],
        "vitals": {"spo2": 95, "sbp": 120},
    }
    result = start(payload)
    assert result["triage"]["acuity_ad"] == "B"
    assert result["triage"]["ctas_compat"] == 2
    assert result["triage"]["green_channel"] is True
    assert result["triage"]["level_1_4"] == 2
    assert "green_channel" in result["triage"]["hooks"]


def test_fast_positive_stroke():
    payload = {
        "patient_id": "p2",
        "chief_complaint": "FAST positive with slurred speech",
        "symptoms": ["stroke signs"],
        "vitals": {"spo2": 96, "sbp": 140},
    }
    result = start(payload)
    assert result["triage"]["acuity_ad"] == "B"
    assert result["triage"]["green_channel"] is True
    assert result["final_state"] == "UNDER_EVALUATION"


def test_mild_sprain_low_acuity():
    payload = {
        "patient_id": "p3",
        "chief_complaint": "mild ankle sprain",
        "symptoms": ["mild sprain"],
        "vitals": {"spo2": 99, "sbp": 125},
    }
    result = start(payload)
    assert result["triage"]["acuity_ad"] == "D"
    assert result["final_state"] == "WAITING_FOR_PHYSICIAN"


def test_yellow_zone_wait_cap_hook():
    payload = {
        "patient_id": "p3b",
        "chief_complaint": "abdominal pain",
        "symptoms": ["needs blood test", "needs CT"],
        "vitals": {"spo2": 98, "sbp": 122},
    }
    result = start(payload)
    assert result["triage"]["zone"] == "yellow"
    assert result["triage"]["max_wait_minutes"] == 30
    assert "wait_cap_30m" in result["triage"]["hooks"]


def test_low_spo2_override():
    payload = {
        "patient_id": "p4",
        "chief_complaint": "fever and dizziness",
        "symptoms": ["fatigue"],
        "vitals": {"spo2": 86, "sbp": 112},
    }
    result = start(payload)
    assert result["triage"]["acuity_ad"] == "B"
    assert "abnormal_vitals" in result["triage"]["hooks"]


def test_illegal_transition_rejected():
    machine = EncounterStateMachine()
    try:
        machine.transition("UNDER_TREATMENT")
    except ValueError as exc:
        assert "Illegal transition" in str(exc)
    else:
        raise AssertionError("expected illegal transition error")


def test_deterministic_replay():
    payload = {
        "patient_id": "p5",
        "chief_complaint": "chest pain",
        "symptoms": ["cold sweat"],
        "vitals": {"spo2": 93, "sbp": 118},
    }
    assert start(payload) == start(payload)
