from __future__ import annotations

from scripts.run_his_stemi_golden_path import build_stemi_golden_path_plan


def test_stemi_golden_path_smoke_runs_full_his_chain() -> None:
    plan = build_stemi_golden_path_plan()
    assert plan["status"] == "passed"
    assert plan["final_phase"] == "DONE"
    assert plan["stemi_workup_counts"]["orders"] >= 1
    assert "memory_replay" in plan["timeline_sections"]
