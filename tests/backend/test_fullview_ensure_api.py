from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_fullview_module():
    path = Path("/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/dev-server.py")
    spec = importlib.util.spec_from_file_location("fullview_dev_server_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_handle_ensure_patient_is_idempotent(tmp_path):
    module = _load_fullview_module()

    map_file = tmp_path / "map-config.json"
    patients_file = tmp_path / "patients.json"
    staff_file = tmp_path / "staff.json"
    room_state_file = tmp_path / "room-state.json"
    event_log_file = tmp_path / "event-log.json"
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    map_file.write_text(json.dumps({
        "floors": [
            {
                "id": 1,
                "label": "1F",
                "rooms": [
                    {"id": "ed_waiting", "label": "ED Waiting", "kind": "waiting", "items": []},
                    {"id": "ed_registration", "label": "ED Registration", "kind": "registration", "items": []},
                ],
            }
        ]
    }), encoding="utf-8")
    patients_file.write_text(json.dumps({"patients": []}), encoding="utf-8")
    staff_file.write_text(json.dumps({"staff": []}), encoding="utf-8")
    room_state_file.write_text(json.dumps({"rooms": {}}), encoding="utf-8")
    event_log_file.write_text(json.dumps({"lastSeq": 0, "events": []}), encoding="utf-8")

    module.MAP_CONFIG = map_file
    module.PATIENTS_FILE = patients_file
    module.STAFF_FILE = staff_file
    module.ROOM_STATE_FILE = room_state_file
    module.EVENT_LOG_FILE = event_log_file
    module.RULES_DIR = rules_dir

    payload = {
        "source": "edmas",
        "external_patient_id": "P-TEST-001",
        "external_case_id": "ENC-TEST-001",
        "department": "emergency",
        "name": "Patient 1",
        "chief_complaint": "chest pain",
        "ctas_level": 2,
        "current_fullview_room_id": "ed_waiting",
        "context": {"edmas_case_id": "ENC-TEST-001"},
    }
    first = module.handle_ensure_patient(payload)
    second = module.handle_ensure_patient(payload)

    assert first["accepted"] is True
    assert first["created"] is True
    assert second["accepted"] is True
    assert second["created"] is False
    persisted = json.loads(patients_file.read_text(encoding="utf-8"))
    assert len(persisted["patients"]) == 1
    assert persisted["patients"][0]["patientId"] == "P-TEST-001"
    assert persisted["patients"][0]["externalCaseId"] == "ENC-TEST-001"
