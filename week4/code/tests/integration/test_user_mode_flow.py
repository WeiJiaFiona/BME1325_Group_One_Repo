from fastapi.testclient import TestClient
from app.main import app


def test_user_patient_flow_returns_zone_and_next_action():
    client = TestClient(app)
    payload = {"chief_complaint": "胸痛", "vitals": {"spo2": 95}, "resource_need": 2}
    resp = client.post('/mode/user/encounter/start', json=payload)
    data = resp.json()
    assert resp.status_code == 200
    assert data['zone'] in ['red', 'yellow', 'green']
    assert 'next_action' in data
