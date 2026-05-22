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


class TestProcessEnvironmentEndpoint(TestCase):
    def test_process_environment_writes_snapshot(self):
        with tempfile.TemporaryDirectory() as storage_dir, tempfile.TemporaryDirectory() as temp_dir:
            sim_code = "process-ok"

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "reverie"), exist_ok=True)
            with open(os.path.join(storage_dir, sim_code, "reverie", "maze_visuals.json"), "w", encoding="utf-8") as f:
                json.dump({"width": 20, "height": 20}, f)

            payload = {
                "step": 1,
                "sim_code": sim_code,
                "environment": {
                    "Patient 1": {
                        "maze": "ed_map",
                        "x": 3,
                        "y": 4,
                        "name": "Patient 1",
                        "role": "patient",
                        "persona_role": "patient",
                        "act": "idle",
                    },
                },
            }

            with patch("translator.views._storage_path", side_effect=fake_storage_path), \
                 patch("translator.views._temp_path", side_effect=fake_temp_path):
                response = self.client.post(
                    "/process_environment/",
                    data=json.dumps(payload),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertTrue(data["ok"])
            stored_path = os.path.join(storage_dir, sim_code, "environment", "1.json")
            self.assertTrue(os.path.exists(stored_path))
            with open(stored_path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            self.assertIn("Patient 1", stored)
            self.assertEqual(stored["Patient 1"]["name"], "Patient 1")
            self.assertEqual(stored["Patient 1"]["role"], "patient")
            self.assertEqual(stored["Patient 1"]["persona_role"], "patient")
            self.assertEqual(stored["Patient 1"]["act"], "idle")
            log_path = os.path.join(temp_dir, "bridge_requests.jsonl")
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(entries[-1]["path"], "/process_environment/")
            self.assertEqual(entries[-1]["step"], 1)
            self.assertTrue(entries[-1]["ok"])

    def test_process_environment_rejects_invalid_json(self):
        response = self.client.post(
            "/process_environment/",
            data="{invalid-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["ok"])
        self.assertIn("invalid JSON", data["error"])

    def test_process_environment_rejects_missing_fields(self):
        response = self.client.post(
            "/process_environment/",
            data=json.dumps({"step": 1, "sim_code": "curr_sim"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["ok"])
        self.assertIn("missing required fields", data["error"])

    def test_short_sync_path_update_then_process_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "sync-short"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "reverie"), exist_ok=True)

            with open(os.path.join(storage_dir, sim_code, "reverie", "maze_visuals.json"), "w", encoding="utf-8") as f:
                json.dump({"width": 50, "height": 50}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 2}, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "2.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 13:00:00"}}, f)

            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)
            with open(os.path.join(temp_dir, "curr_step.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 2}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                update_resp = self.client.post(
                    "/update_environment/",
                    data=json.dumps({"step": 2, "sim_code": sim_code}),
                    content_type="application/json",
                )
                self.assertEqual(update_resp.status_code, 200)
                update_payload = json.loads(update_resp.content)
                self.assertEqual(update_payload["<step>"], 2)

                process_resp = self.client.post(
                    "/process_environment/",
                    data=json.dumps({
                        "step": 2,
                        "sim_code": sim_code,
                        "environment": {"Patient 1": {"maze": "ed_map", "x": 6, "y": 7}},
                    }),
                    content_type="application/json",
                )
                self.assertEqual(process_resp.status_code, 200)
                self.assertTrue(json.loads(process_resp.content)["ok"])

                dashboard_resp = self.client.get("/api/live_dashboard/")

            self.assertEqual(dashboard_resp.status_code, 200)
            dashboard = json.loads(dashboard_resp.content)
            self.assertEqual(dashboard["runtime_sync"]["latest_movement_step"], 2)
            self.assertEqual(dashboard["runtime_sync"]["latest_environment_step"], 2)
            self.assertTrue(dashboard["runtime_sync"]["in_sync"])

    def test_update_environment_logs_bridge_request(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "update-log"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            with open(os.path.join(storage_dir, sim_code, "movement", "3.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 13:00:00"}}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.post(
                    "/update_environment/",
                    data=json.dumps({"step": 3, "sim_code": sim_code}),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            payload = json.loads(response.content)
            self.assertEqual(payload["<step>"], 3)
            log_path = os.path.join(temp_dir, "bridge_requests.jsonl")
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(entries[-1]["path"], "/update_environment/")
        self.assertEqual(entries[-1]["step"], 3)
        self.assertTrue(entries[-1]["ok"])


class TestRuntimeCleanupHelpers(TestCase):
    def test_cleanup_stale_runtime_state_removes_temp_files_but_preserves_bridge_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            os.makedirs(os.path.join(temp_dir, "commands"), exist_ok=True)
            Path(os.path.join(temp_dir, "commands", "cmd_1.json")).write_text("{}", encoding="utf-8")
            Path(os.path.join(temp_dir, "curr_step.json")).write_text('{"step": 4}', encoding="utf-8")
            Path(os.path.join(temp_dir, "curr_sim_code.json")).write_text('{"sim_code": "curr_sim"}', encoding="utf-8")
            Path(os.path.join(temp_dir, "sim_output.json")).write_text('{"outputs": []}', encoding="utf-8")
            Path(os.path.join(temp_dir, "bridge_requests.jsonl")).write_text('{"ok": true}\n', encoding="utf-8")

            with patch("translator.views._temp_path", side_effect=fake_temp_path):
                from translator import views

                views._cleanup_stale_runtime_state()

            self.assertFalse(Path(os.path.join(temp_dir, "curr_step.json")).exists())
            self.assertFalse(Path(os.path.join(temp_dir, "curr_sim_code.json")).exists())
            self.assertFalse(Path(os.path.join(temp_dir, "sim_output.json")).exists())
            self.assertFalse(Path(os.path.join(temp_dir, "commands", "cmd_1.json")).exists())
            self.assertTrue(Path(os.path.join(temp_dir, "bridge_requests.jsonl")).exists())

    def test_reset_runtime_state_removes_dialogue_trace_file(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "reset-dialogue-trace"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)
            Path(os.path.join(storage_dir, sim_code, "movement", "0.json")).write_text("{}", encoding="utf-8")
            Path(os.path.join(storage_dir, sim_code, "environment", "0.json")).write_text("{}", encoding="utf-8")
            Path(os.path.join(storage_dir, sim_code, "dialogue_trace.jsonl")).write_text('{"step":0}\n', encoding="utf-8")

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                from translator import views

                trace = views._reset_runtime_state_for_new_run(sim_code, requested_seed=123)

            self.assertFalse(Path(os.path.join(storage_dir, sim_code, "movement", "0.json")).exists())
            self.assertFalse(Path(os.path.join(storage_dir, sim_code, "environment", "0.json")).exists())
            self.assertFalse(Path(os.path.join(storage_dir, sim_code, "dialogue_trace.jsonl")).exists())
            self.assertEqual(trace.get("requested_seed"), 123)
            self.assertTrue(trace.get("run_id"))


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
            self.assertIn("backend_health", data)
            self.assertIn("runtime_trace", data)
            self.assertEqual(data["runtime_sync"]["status_step"], 3)
            self.assertEqual(data["runtime_sync"]["curr_step_pointer"], 4)
            self.assertEqual(data["runtime_sync"]["latest_movement_step"], 3)
            self.assertEqual(data["runtime_sync"]["latest_environment_step"], 4)
            self.assertTrue(data["runtime_sync"]["in_sync"])
            self.assertEqual(data["runtime_trace"]["backend_movement_max_step"], 3)
            self.assertEqual(data["runtime_trace"]["frontend_environment_max_step"], 4)
            self.assertIn("backend_alive", data["backend_health"])
            self.assertIsInstance(data["backend_health"]["backend_alive"], bool)

    def test_live_dashboard_api_backfills_runtime_trace_run_id(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "runid-sim"

            def fake_temp_path(*parts):
                return os.path.join(temp_dir, *parts)

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)
            with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
                json.dump({"sim_code": sim_code}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 1}, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "1.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {}}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "1.json"), "w", encoding="utf-8") as f:
                json.dump({}, f)
            with open(os.path.join(storage_dir, sim_code, "runtime_trace.json"), "w", encoding="utf-8") as f:
                json.dump({"run_id": None, "backend_movement_max_step": 1}, f)

            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/api/live_dashboard/")

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertTrue(data["runtime_trace"]["run_id"])

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
            self.assertIn("backend_health", data)


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
            self.assertContains(response, "Render step")
            self.assertContains(response, "playback step")
            context = response.context or getattr(response, "context_data", None)
            self.assertIsNotNone(context)
            self.assertEqual(context["runtime_sources"]["status_step"], 0)
            self.assertEqual(context["render_step"], 0)
            self.assertEqual(context["playback_step"], 1)
            self.assertContains(response, "run 10")

    def test_auto_mode_clamps_render_baseline_when_environment_ahead_of_movement(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "auto-render-baseline"

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
                json.dump({"step": 0}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "0.json"), "w", encoding="utf-8") as f:
                json.dump({"Patient 1": {"x": 1, "y": 2}}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "4.json"), "w", encoding="utf-8") as f:
                json.dump({"Patient 1": {"x": 7, "y": 9}}, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "0.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 12:00:00"}}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 0}, f)
            with open(os.path.join(storage_dir, sim_code, "reverie", "maze_visuals.json"), "w", encoding="utf-8") as f:
                json.dump({"width": 10, "height": 8}, f)

            with patch.dict(os.environ, {"EDSIM_MODE": "auto"}), \
                 patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/simulator_home?ui_mode=auto")

            self.assertEqual(response.status_code, 200)
            context = response.context or getattr(response, "context_data", None)
            self.assertIsNotNone(context)
            self.assertEqual(context["render_step"], 0)
            self.assertEqual(context["playback_step"], 1)
            self.assertEqual(context["step"], 0)
            self.assertEqual(context["persona_init_pos"], [["Patient 1", 1, 2]])
            self.assertIn("Environment snapshots were ahead of movement", context["runtime_alignment_note"])

    def test_auto_mode_uses_latest_shared_step_when_environment_and_movement_align(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "auto-render-aligned"

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
                json.dump({"step": 4}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "0.json"), "w", encoding="utf-8") as f:
                json.dump({"Patient 1": {"x": 1, "y": 2}}, f)
            with open(os.path.join(storage_dir, sim_code, "environment", "4.json"), "w", encoding="utf-8") as f:
                json.dump({"Patient 1": {"x": 7, "y": 9}}, f)
            with open(os.path.join(storage_dir, sim_code, "movement", "4.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 12:00:00"}}, f)
            with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 4}, f)
            with open(os.path.join(storage_dir, sim_code, "reverie", "maze_visuals.json"), "w", encoding="utf-8") as f:
                json.dump({"width": 10, "height": 8}, f)

            with patch.dict(os.environ, {"EDSIM_MODE": "auto"}), \
                 patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path):
                response = self.client.get("/simulator_home?ui_mode=auto")

            self.assertEqual(response.status_code, 200)
            context = response.context or getattr(response, "context_data", None)
            self.assertIsNotNone(context)
            self.assertEqual(context["render_step"], 4)
            self.assertEqual(context["playback_step"], 5)
            self.assertEqual(context["step"], 4)
            self.assertEqual(context["persona_init_pos"], [["Patient 1", 7, 9]])
            self.assertEqual(context["runtime_alignment_note"], "")


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


class TestSaveSimulationSettings(TestCase):
    def test_missing_seed_persists_null_and_resets_runtime(self):
        with tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "ed_sim_n5"
            curr_sim_code = "curr_sim"

            def fake_storage_path(*parts):
                return os.path.join(storage_dir, *parts)

            os.makedirs(os.path.join(storage_dir, sim_code, "reverie"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, curr_sim_code, "movement"), exist_ok=True)
            os.makedirs(os.path.join(storage_dir, curr_sim_code, "environment"), exist_ok=True)
            meta_path = os.path.join(storage_dir, sim_code, "reverie", "meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"seed": None, "doctor_starting_amount": 1}, f)
            with open(os.path.join(storage_dir, curr_sim_code, "movement", "5.json"), "w", encoding="utf-8") as f:
                json.dump({"persona": {}}, f)
            with open(os.path.join(storage_dir, curr_sim_code, "environment", "5.json"), "w", encoding="utf-8") as f:
                json.dump({}, f)
            with open(os.path.join(storage_dir, curr_sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
                json.dump({"step": 5}, f)

            with tempfile.TemporaryDirectory() as temp_dir, \
                 patch("translator.views._storage_path", side_effect=fake_storage_path), \
                 patch("translator.views._temp_path", side_effect=lambda *parts: os.path.join(temp_dir, *parts)), \
                 patch("translator.views._ensure_seed_sim_storage"):
                with open(os.path.join(temp_dir, "curr_step.json"), "w", encoding="utf-8") as f:
                    json.dump({"step": 6}, f)
                response = self.client.post(
                    "/save_simulation_settings/",
                    data=json.dumps({"doctor_starting_amount": 2}),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 200)
            payload = json.loads(response.content)
            self.assertTrue(payload["ok"])
            with open(meta_path, "r", encoding="utf-8") as f:
                updated_meta = json.load(f)
            self.assertIsNone(updated_meta["seed"])
            self.assertEqual(updated_meta["doctor_starting_amount"], 2)
            self.assertFalse(os.path.exists(os.path.join(storage_dir, curr_sim_code, "movement", "5.json")))
            self.assertFalse(os.path.exists(os.path.join(storage_dir, curr_sim_code, "environment", "5.json")))
            self.assertFalse(os.path.exists(os.path.join(storage_dir, curr_sim_code, "sim_status.json")))
            trace_path = os.path.join(storage_dir, curr_sim_code, "runtime_trace.json")
            self.assertTrue(os.path.exists(trace_path))
            with open(trace_path, "r", encoding="utf-8") as f:
                trace_payload = json.load(f)
            self.assertIn("run_id", trace_payload)
            self.assertEqual(trace_payload["requested_seed"], None)


class TestStartBackendSingleInstance(TestCase):
    @patch("translator.views._list_running_reverie_processes", return_value=[4321, 8765])
    @patch("translator.views._runtime_backend_health", return_value={
        "backend_alive": True,
        "running_pids": [4321, 8765],
        "pending_command_count": 0,
        "pending_command_ids": [],
        "last_command_timestamp": None,
        "last_progress_timestamp": None,
        "progress_age_seconds": None,
        "stalled": False,
    })
    @patch("translator.views._resolve_backend_dir")
    def test_start_backend_reuses_existing_reverie_process(self, mock_backend_dir, mock_health, mock_running):
        with tempfile.TemporaryDirectory() as backend_dir:
            mock_backend_dir.return_value = Path(backend_dir)
            response = self.client.post("/start_backend/ed_sim_n5/curr_sim/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["ok"], 4321)
        self.assertTrue(data["already_running"])
        self.assertEqual(data["running_pids"], [4321, 8765])
