import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from django.test import Client, TestCase


@pytest.fixture
def client():
    return Client()


class TestLandingView(TestCase):
    def test_landing_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class TestPathTesterView(TestCase):
    def test_path_tester_returns_200(self):
        response = self.client.get("/path_tester/")
        self.assertEqual(response.status_code, 200)


class TestGetSimOutput(TestCase):
    def test_returns_empty_outputs_when_file_absent(self, tmp_path=None):
        # Isolate TEMP_ROOT so prior regression runs cannot leak sim_output.json
        # into this test's expectations.
        with tempfile.TemporaryDirectory() as temp_dir:
            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            with patch("translator.views._temp_path", side_effect=fake_temp_path):
                response = self.client.get("/get_sim_output/")
                self.assertEqual(response.status_code, 200)
                data = json.loads(response.content)
                self.assertIn("outputs", data)
                self.assertEqual(data["outputs"], [])


class TestSendSimCommand(TestCase):
    def test_valid_command_returns_ok(self):
        response = self.client.post(
            "/send_sim_command/",
            data=json.dumps({"command": "run 10"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get("ok"))
        self.assertIn("id", data)

    def test_missing_command_returns_400(self):
        response = self.client.post(
            "/send_sim_command/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data.get("ok"))


class TestDashboardRuntimeSync(TestCase):
    def test_live_dashboard_api_exposes_runtime_sync_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "sync-sim"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)

            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)
            with open(os.path.join(temp_dir, "curr_step.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 4}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "step": 3,
                    "sim_time": "Apr 20 2026  10:00",
                    "current_patients": 2,
                    "completed": 1,
                    "patient_states": {},
                    "zone_occupancy": {},
                    "queues": {},
                    "resources": {},
                    "nurse_status": {},
                    "doctor_assigned": {},
                }, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "3.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 10:00:00"}}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "4.json"), "w", encoding="utf-8") as f:
                json.dump({}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/api/live_dashboard/")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertIn("runtime_sync", data)
            self.assertEqual(data["runtime_sync"]["status_step"], 3)
            self.assertEqual(data["runtime_sync"]["curr_step_pointer"], 4)
            self.assertEqual(data["runtime_sync"]["latest_movement_step"], 3)
            self.assertEqual(data["runtime_sync"]["latest_environment_step"], 4)
            self.assertTrue(data["runtime_sync"]["in_sync"])

    def test_live_dashboard_api_flags_step_lag(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "lag-sim"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)

            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)
            with open(os.path.join(temp_dir, "curr_step.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 9}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "step": 3,
                    "sim_time": "Apr 20 2026  11:00",
                    "current_patients": 1,
                    "completed": 0,
                    "patient_states": {},
                    "zone_occupancy": {},
                    "queues": {},
                    "resources": {},
                    "nurse_status": {},
                    "doctor_assigned": {},
                }, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "2.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 11:00:00"}}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "7.json"), "w", encoding="utf-8") as f:
                json.dump({}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/api/live_dashboard/")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertFalse(data["runtime_sync"]["in_sync"])


class TestHomeRuntimeMessaging(TestCase):
    def test_home_page_labels_command_console_and_data_source_note(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "home-sim"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "personas", "Patient 1"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "reverie"), exist_ok=True)

            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)
            with open(os.path.join(temp_dir, "curr_step.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 1}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "0.json"), "w", encoding="utf-8") as f:
                json.dump({"Patient 1": {"x": 1, "y": 2}}, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "0.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 12:00:00"}}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 0}, f)
            with open(os.path.join(storage_dir, sim_code, "reverie", "maze_visuals.json"), "w", encoding="utf-8") as f:
                json.dump({"width": 10, "height": 8}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/simulator_home")

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Command Console")
            self.assertContains(response, "sim_status.json")
            self.assertContains(response, "curr_step.json")
            self.assertEqual(response.context["runtime_sources"]["status_step"], 0)
            self.assertContains(response, "run 10")


class TestDataVisualizationAPI(TestCase):
    def test_state_times_api_defaults_to_active_sim_code(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "active-data-sim"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "reverie"), exist_ok=True)
            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)

            state_times = "\n".join([
                "name,CTAS,WAITING_FOR_TRIAGE,TRIAGE,WAITING_FOR_NURSE,WAITING_FOR_FIRST_ASSESSMENT,WAITING_FOR_TEST,GOING_FOR_TEST,WAITING_FOR_RESULT,WAITING_FOR_DOCTOR,LEAVING",
                "Patient 1,3,5,3,2,4,6,2,7,8,1",
                "Patient 2,4,2,1,1,3,0,0,0,5,1",
            ])
            with open(os.path.join(storage_dir, sim_code, "reverie", "state_times.csv"), "w", encoding="utf-8") as f:
                f.write(state_times)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/api/state_times/")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertIn("waiting", data)
            self.assertIn("treatment", data)
            self.assertIn("ed", data)
            self.assertIn("CTAS 3", data["waiting"])

    def test_state_times_api_reports_missing_saved_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "missing-data-sim"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/api/state_times/")

            self.assertEqual(response.status_code, 404)
            data = json.loads(response.content)
            self.assertFalse(data["ok"])
            self.assertIn("state_times.csv", data["error"])


class TestStartBackendSingleInstance(TestCase):
    @patch("translator.views._list_running_reverie_processes", return_value=[4321, 8765])
    @patch("translator.views._resolve_backend_dir")
    def test_start_backend_reuses_existing_reverie_process(self, mock_backend_dir, mock_running):
        with tempfile.TemporaryDirectory() as backend_dir:
            mock_backend_dir.return_value = Path(backend_dir)
            response = self.client.post("/start_backend/ed_sim_n5/curr_sim/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["ok"], 4321)
        self.assertTrue(data["already_running"])
        self.assertEqual(data["running_pids"], [4321, 8765])
