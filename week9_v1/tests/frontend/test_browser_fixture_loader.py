import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase


class TestBrowserFixtureLoader(TestCase):
    def _seed_fixture_root(self, root: Path, fixture_name: str, sim_code: str):
        fixture_root = root / fixture_name
        storage_dir = fixture_root / "storage" / sim_code
        temp_dir = fixture_root / "temp_storage"
        (storage_dir / "environment").mkdir(parents=True, exist_ok=True)
        (storage_dir / "movement").mkdir(parents=True, exist_ok=True)
        (storage_dir / "reverie").mkdir(parents=True, exist_ok=True)
        (storage_dir / "personas" / "Patient 1").mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / "environment" / "0.json").write_text(json.dumps({"Patient 1": {"x": 1, "y": 1}}), encoding="utf-8")
        (storage_dir / "movement" / "0.json").write_text(
            json.dumps({"persona": {"Patient 1": {"movement": [1, 1], "movement_path": []}}, "meta": {"curr_time": "Apr 20, 2026, 12:00:00"}}),
            encoding="utf-8",
        )
        (storage_dir / "reverie" / "maze_visuals.json").write_text(json.dumps({"width": 8, "height": 8}), encoding="utf-8")
        (storage_dir / "sim_status.json").write_text(json.dumps({"step": 0}), encoding="utf-8")
        (temp_dir / "curr_sim_code.json").write_text(json.dumps({"sim_code": sim_code}), encoding="utf-8")
        (temp_dir / "curr_step.json").write_text(json.dumps({"step": 0}), encoding="utf-8")
        return fixture_root

    def test_fixture_loader_copies_fixture_into_runtime_paths(self):
        with tempfile.TemporaryDirectory() as fixture_dir, tempfile.TemporaryDirectory() as storage_dir, tempfile.TemporaryDirectory() as temp_dir:
            sim_code = "fixture-loader-sim"
            self._seed_fixture_root(Path(fixture_dir), "loader_case", sim_code)
            with patch.dict(os.environ, {"EDSIM_TEST_MODE": "1"}), \
                 patch("translator.views._browser_fixture_root", return_value=Path(fixture_dir)), \
                 patch("translator.views.STORAGE_ROOT", Path(storage_dir)), \
                 patch("translator.views.TEMP_ROOT", Path(temp_dir)):
                response = self.client.post(
                    "/test/load_fixture/",
                    data=json.dumps({"fixture": "loader_case"}),
                    content_type="application/json",
                )
                payload = json.loads(response.content)
                storage_exists = (Path(storage_dir) / sim_code / "environment" / "0.json").exists()
                temp_exists = (Path(temp_dir) / "curr_sim_code.json").exists()

            self.assertEqual(response.status_code, 200)
            self.assertTrue(storage_exists)
            self.assertTrue(temp_exists)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sim_code"], sim_code)
        self.assertTrue(payload["runtime_sync"]["in_sync"])

    def test_home_allows_test_backend_mode_override(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as storage_dir:
            sim_code = "mode-override-sim"
            (Path(storage_dir) / sim_code / "personas" / "Patient 1").mkdir(parents=True, exist_ok=True)
            (Path(storage_dir) / sim_code / "environment").mkdir(parents=True, exist_ok=True)
            (Path(storage_dir) / sim_code / "movement").mkdir(parents=True, exist_ok=True)
            (Path(storage_dir) / sim_code / "reverie").mkdir(parents=True, exist_ok=True)
            (Path(temp_dir) / "curr_sim_code.json").write_text(json.dumps({"sim_code": sim_code}), encoding="utf-8")
            (Path(temp_dir) / "curr_step.json").write_text(json.dumps({"step": 0}), encoding="utf-8")
            (Path(storage_dir) / sim_code / "environment" / "0.json").write_text(json.dumps({"Patient 1": {"x": 1, "y": 1}}), encoding="utf-8")
            (Path(storage_dir) / sim_code / "movement" / "0.json").write_text(json.dumps({"persona": {}, "meta": {"curr_time": "Apr 20, 2026, 12:00:00"}}), encoding="utf-8")
            (Path(storage_dir) / sim_code / "reverie" / "maze_visuals.json").write_text(json.dumps({"width": 8, "height": 8}), encoding="utf-8")
            (Path(storage_dir) / sim_code / "sim_status.json").write_text(json.dumps({"step": 0}), encoding="utf-8")

            with patch.dict(os.environ, {"EDSIM_TEST_MODE": "1", "EDSIM_MODE": "auto"}), \
                 patch("translator.views.STORAGE_ROOT", Path(storage_dir)), \
                 patch("translator.views.TEMP_ROOT", Path(temp_dir)):
                response = self.client.get("/simulator_home?ui_mode=user&__test_backend_mode=user")

        self.assertEqual(response.status_code, 200)
        context = response.context or getattr(response, "context_data", None)
        self.assertEqual(context["effective_ui_mode"], "user")
