from __future__ import annotations

from app_core.his.adapters import get_memory_to_his_mapping_expectation, get_memory_upgrade_plan
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem


def test_memory_upgrade_expectation_tracks_frozen_inputs() -> None:
    expectation = get_memory_to_his_mapping_expectation()
    assert expectation.accepted_inputs == (
        MemoryItem,
        CurrentEncounterSummary,
        HandoffMemorySnapshot,
    )


def test_memory_upgrade_plan_uses_frozen_his_targets_only() -> None:
    targets = {plan.target_table for plan in get_memory_upgrade_plan()}
    assert {"memory_events", "event_registry", "current_encounter_summaries", "handoff_snapshots", "clinical_documents"} <= targets
