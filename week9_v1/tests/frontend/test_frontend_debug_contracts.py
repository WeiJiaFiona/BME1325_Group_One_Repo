import json
import os
import tempfile
from unittest.mock import patch

from django.test import TestCase


class TestFrontendDebugContracts(TestCase):
    def _fake_paths(self, temp_dir, storage_dir):
        def fake_temp_path(*parts):
            return os.path.join(temp_dir, *parts)

        def fake_storage_path(*parts):
            return os.path.join(storage_dir, *parts)

        return fake_temp_path, fake_storage_path

    def _seed_runtime(self, temp_dir, storage_dir, sim_code="debug-sim"):
        os.makedirs(os.path.join(storage_dir, sim_code, "personas", "Patient 1"), exist_ok=True)
        os.makedirs(os.path.join(storage_dir, sim_code, "movement"), exist_ok=True)
        os.makedirs(os.path.join(storage_dir, sim_code, "environment"), exist_ok=True)
        os.makedirs(os.path.join(storage_dir, sim_code, "reverie"), exist_ok=True)
        with open(os.path.join(temp_dir, "curr_sim_code.json"), "w", encoding="utf-8") as f:
            json.dump({"sim_code": sim_code}, f)
        with open(os.path.join(temp_dir, "curr_step.json"), "w", encoding="utf-8") as f:
            json.dump({"step": 0}, f)
        with open(os.path.join(storage_dir, sim_code, "environment", "0.json"), "w", encoding="utf-8") as f:
            json.dump({"Patient 1": {"x": 1, "y": 2}, "Doctor 1": {"x": 2, "y": 2}}, f)
        with open(os.path.join(storage_dir, sim_code, "movement", "0.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "persona": {
                        "Patient 1": {
                            "movement": [1, 2],
                            "movement_path": [[1, 2]],
                            "description": "waiting@triage queue",
                            "chat": None,
                            "pronunciatio": "",
                        }
                    },
                    "meta": {"curr_time": "Apr 20, 2026, 12:00:00"},
                },
                f,
            )
        with open(os.path.join(storage_dir, sim_code, "sim_status.json"), "w", encoding="utf-8") as f:
            json.dump({"step": 0}, f)
        with open(os.path.join(storage_dir, sim_code, "reverie", "maze_visuals.json"), "w", encoding="utf-8") as f:
            json.dump({"width": 10, "height": 8}, f)

    def test_user_mode_home_includes_avatar_and_path_debug_contracts(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            fake_temp_path, fake_storage_path = self._fake_paths(temp_dir, storage_dir)
            self._seed_runtime(temp_dir, storage_dir)
            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path), \
                 patch("translator.views._backend_mode", return_value="user"):
                response = self.client.get("/simulator_home?ui_mode=user")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "movementPathQueue")
        self.assertContains(response, "avatarKey")
        self.assertContains(response, "spriteKey")
        self.assertContains(response, "badgeTag")
        self.assertContains(response, "queueLength")
        self.assertContains(response, "currentTargetTile")
        self.assertContains(response, "settledTile")
        self.assertContains(response, "spawnOrder")
        self.assertContains(response, "data-role-key")
        self.assertContains(response, "Doctor_1")
        self.assertContains(response, "Patient_1")
        self.assertContains(response, "role_doctor")
        self.assertContains(response, "role_patient")
        self.assertContains(response, "missing_or_invalid_path")

    def test_auto_mode_home_includes_avatar_and_path_debug_contracts(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            fake_temp_path, fake_storage_path = self._fake_paths(temp_dir, storage_dir)
            self._seed_runtime(temp_dir, storage_dir)
            with patch("translator.views._temp_path", side_effect=fake_temp_path), \
                 patch("translator.views._storage_path", side_effect=fake_storage_path), \
                 patch("translator.views._backend_mode", return_value="auto"):
                response = self.client.get("/simulator_home?ui_mode=auto")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "movementPathQueue")
        self.assertContains(response, "avatarKey")
        self.assertContains(response, "spriteKey")
        self.assertContains(response, "badgeTag")
        self.assertContains(response, "backendHealth")
        self.assertContains(response, "queueLength")
        self.assertContains(response, "currentTargetTile")
        self.assertContains(response, "settledTile")
        self.assertContains(response, "spawnOrder")
        self.assertContains(response, "data-role-key")
        self.assertContains(response, "Doctor_1")
        self.assertContains(response, "Patient_1")
        self.assertContains(response, "role_doctor")
        self.assertContains(response, "role_patient")
        context = response.context or getattr(response, "context_data", None)
        self.assertEqual(context["effective_ui_mode"], "auto")
