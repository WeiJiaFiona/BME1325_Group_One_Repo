from __future__ import annotations

import runpy
from pathlib import Path


def test_timeline_export_smoke_plan_is_present() -> None:
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "scripts" / "run_his_timeline_export_smoke.py"))
    plan = namespace["build_timeline_export_smoke_plan"]()
    assert plan["status"] == "placeholder"
    assert "replay_exports" in plan["reserved_targets"]
