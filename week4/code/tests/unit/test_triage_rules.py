from app.domain.triage_rules import triage_level, route_zone


def test_level_1_route_red():
    patient = {"vitals": {"spo2": 82}, "chief_complaint": "呼吸困难"}
    level = triage_level(patient)
    zone = route_zone(level)
    assert level == 1
    assert zone == "red"


def test_level_4_route_green():
    patient = {"vitals": {"spo2": 98}, "chief_complaint": "轻微擦伤", "resource_need": 1}
    level = triage_level(patient)
    zone = route_zone(level)
    assert level == 4
    assert zone == "green"
