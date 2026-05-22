from __future__ import annotations

from scripts.run_his_timeline_export_smoke import build_timeline_export_smoke_plan


def test_timeline_export_smoke_plan_runs_real_bundle() -> None:
    plan = build_timeline_export_smoke_plan()
    assert plan["status"] == "passed"
    assert plan["counts"]["event_registry"] >= 4
    assert plan["counts"]["handoff_snapshots"] >= 2
    assert plan["counts"]["memory_events"] >= 4
    assert plan["timeline_document_type"] == "timeline_export"
