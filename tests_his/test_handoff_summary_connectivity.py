from __future__ import annotations

from app_core.his.adapters import get_memory_upgrade_plan


def test_handoff_and_summary_targets_exist_in_placeholder_plan() -> None:
    targets = {plan.target_table for plan in get_memory_upgrade_plan()}
    assert "current_encounter_summaries" in targets
    assert "handoff_snapshots" in targets
    assert "clinical_documents" in targets
