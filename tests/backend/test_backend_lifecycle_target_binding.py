import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client


class _FakePopen:
    def __init__(self, pid=999):
        self.pid = pid

    def poll(self):
        return None


def _backend_dir():
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "backend_server"
    path.mkdir(parents=True, exist_ok=True)
    return tmp, path


def test_existing_backend_same_target_allowed_already_running():
    client = Client()
    tempdir, backend_dir = _backend_dir()
    running_state = {
        "backend_alive": True,
        "running_pids": [123],
        "running_target": "same_target",
        "requested_target": "same_target",
        "target_matches": True,
        "curr_sim_code": "same_target",
    }
    backend_health = {"stalled": False, "backend_alive": True, "running_pids": [123]}
    with patch("translator.views._resolve_backend_dir", return_value=backend_dir), \
         patch("translator.views.detect_running_backend_state", return_value=running_state), \
         patch("translator.views._runtime_backend_health", return_value=backend_health), \
         patch("translator.views._sync_runtime_trace", return_value={}):
        response = client.post("/start_backend/ed_sim_n5/same_target/?headless=1")
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["already_running"] is True
    assert payload["running_target"] == "same_target"
    assert payload["requested_target"] == "same_target"
    assert payload["target_matches"] is True
    tempdir.cleanup()


def test_existing_backend_different_target_not_allowed_to_reuse():
    client = Client()
    tempdir, backend_dir = _backend_dir()
    running_state = {
        "backend_alive": True,
        "running_pids": [123],
        "running_target": "curr_sim",
        "requested_target": "new_target",
        "target_matches": False,
        "curr_sim_code": "curr_sim",
    }
    backend_health = {"stalled": False, "backend_alive": True, "running_pids": [123]}
    shutdown_result = {"ok": False, "results": [{"pid": 123, "status": "access_denied"}], "surviving_pids": [123]}
    with patch("translator.views._resolve_backend_dir", return_value=backend_dir), \
         patch("translator.views.detect_running_backend_state", return_value=running_state), \
         patch("translator.views._runtime_backend_health", return_value=backend_health), \
         patch("translator.views._shutdown_backend_processes_with_results", return_value=shutdown_result):
        response = client.post("/start_backend/ed_sim_n5/new_target/?headless=1")
    assert response.status_code == 503
    payload = json.loads(response.content)
    assert payload["error"] == "stale_backend_target_mismatch"
    assert payload["running_target"] == "curr_sim"
    assert payload["requested_target"] == "new_target"
    assert payload["running_pids"] == [123]
    tempdir.cleanup()


def test_force_shutdown_success_starts_requested_target():
    client = Client()
    tempdir, backend_dir = _backend_dir()
    running_state = {
        "backend_alive": True,
        "running_pids": [123],
        "running_target": "curr_sim",
        "requested_target": "new_target",
        "target_matches": False,
        "curr_sim_code": "curr_sim",
    }
    backend_health_stale = {"stalled": False, "backend_alive": True, "running_pids": [123]}
    post_health = {"stalled": False, "backend_alive": True, "running_pids": [999]}

    def fake_check(path):
        return path.endswith("curr_step.json") or path.endswith("sim_status.json")

    with patch("translator.views._resolve_backend_dir", return_value=backend_dir), \
         patch("translator.views.detect_running_backend_state", return_value=running_state), \
         patch("translator.views._runtime_backend_health", side_effect=[backend_health_stale, post_health, post_health]), \
         patch("translator.views._shutdown_backend_processes_with_results", return_value={"ok": True, "results": [], "surviving_pids": []}), \
         patch("translator.views._sync_meta_to_current_beijing_time"), \
         patch("translator.views._read_runtime_trace", return_value={"run_id": "existing"}), \
         patch("translator.views._sync_runtime_trace", return_value={}), \
         patch("translator.views._current_sim_code", return_value="new_target"), \
         patch("translator.views.check_if_file_exists", side_effect=fake_check), \
         patch("translator.views.os.remove"), \
         patch("translator.views._list_running_reverie_processes", return_value=[999]), \
         patch("translator.views.subprocess.Popen", return_value=_FakePopen(pid=999)):
        response = client.post("/start_backend/ed_sim_n5/new_target/")
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["requested_target"] == "new_target"
    assert payload["running_target"] == "new_target"
    assert payload["target_matches"] is True
    tempdir.cleanup()


def test_start_backend_response_includes_running_and_requested_target():
    client = Client()
    tempdir, backend_dir = _backend_dir()
    running_state = {
        "backend_alive": True,
        "running_pids": [321],
        "running_target": "curr_sim",
        "requested_target": "new_target",
        "target_matches": False,
        "curr_sim_code": "curr_sim",
    }
    backend_health = {"stalled": False, "backend_alive": True, "running_pids": [321]}
    shutdown_result = {"ok": False, "results": [{"pid": 321, "status": "still_alive_after_kill"}], "surviving_pids": [321]}
    with patch("translator.views._resolve_backend_dir", return_value=backend_dir), \
         patch("translator.views.detect_running_backend_state", return_value=running_state), \
         patch("translator.views._runtime_backend_health", return_value=backend_health), \
         patch("translator.views._shutdown_backend_processes_with_results", return_value=shutdown_result):
        response = client.post("/start_backend/ed_sim_n5/new_target/?headless=1")
    payload = json.loads(response.content)
    assert "running_target" in payload
    assert "requested_target" in payload
    assert payload["running_target"] == "curr_sim"
    assert payload["requested_target"] == "new_target"
    tempdir.cleanup()
