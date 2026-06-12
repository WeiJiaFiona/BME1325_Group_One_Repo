from app_core.integration.disposition_rules import compute_mews, decide_ed_disposition, diagnostic_decision
from app_core.integration.fullview_mapping import map_auto_location_to_room, map_user_phase_to_room


def test_user_phase_room_mapping_prefers_high_acuity_room():
    assert map_user_phase_to_room(phase="DOCTOR_CALLED", acuity="A") == "ed_red_resus"
    assert map_user_phase_to_room(phase="DOCTOR_CALLED", acuity="C") == "ed_major"
    assert map_user_phase_to_room(phase="WAITING_CALL", acuity=None) == "ed_waiting"


def test_auto_location_mapping_uses_next_room_and_ctas():
    assert map_auto_location_to_room(zone="major injuries zone", next_room=None, state="WAITING_FOR_DOCTOR", ctas=2) == "ed_major"
    assert map_auto_location_to_room(zone=None, next_room="diagnostic room", state="WAITING_FOR_TEST", ctas=3) == "ed_diagnostic"
    assert map_auto_location_to_room(zone=None, next_room=None, state="WAITING_FOR_DOCTOR", ctas=1) == "ed_red_resus"


def test_disposition_rules_route_critical_patient_to_icu():
    decision = decide_ed_disposition(
        acuity="B",
        ctas=2,
        vitals={"spo2": 86, "sbp": 82, "resp_rate": 32, "heart_rate": 135},
    )
    assert compute_mews({"spo2": 86, "sbp": 82, "resp_rate": 32, "heart_rate": 135}) >= 5
    assert decision.event_id == "TRANSFER_ED_TO_ICU"
    assert decision.to_room_id == "icu_admission"


def test_disposition_rules_route_moderate_patient_to_ward():
    decision = decide_ed_disposition(
        acuity="C",
        ctas=3,
        vitals={"spo2": 95, "sbp": 108, "resp_rate": 20, "heart_rate": 98},
    )
    assert decision.event_id == "TRANSFER_ED_TO_WARD"
    assert decision.to_room_id == "ward_admission"


def test_diagnostic_decision_is_fixed_ed_rule():
    decision = diagnostic_decision()
    assert decision.event_id == "ED_TO_DIAGNOSTIC_MOVE"
    assert decision.to_room_id == "ed_diagnostic"
