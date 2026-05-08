from __future__ import annotations

import runpy
from pathlib import Path


def test_stemi_golden_path_smoke_plan_is_present() -> None:
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "scripts" / "run_his_stemi_golden_path.py"))
    plan = namespace["build_stemi_golden_path_plan"]()
    assert plan["status"] == "placeholder"
    assert "Encounter open" in plan["phases"]
    assert "Timeline export verification" in plan["phases"]
