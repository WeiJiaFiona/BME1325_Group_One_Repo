from __future__ import annotations

from dataclasses import dataclass

from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem


@dataclass(frozen=True)
class MemoryToHisMappingExpectation:
    memory_event_target: tuple[str, ...] = ("memory_events", "event_registry")
    current_summary_target: tuple[str, ...] = ("current_encounter_summaries",)
    handoff_snapshot_target: tuple[str, ...] = ("handoff_snapshots", "clinical_documents")
    accepted_inputs: tuple[type[object], ...] = (
        MemoryItem,
        CurrentEncounterSummary,
        HandoffMemorySnapshot,
    )


def get_memory_to_his_mapping_expectation() -> MemoryToHisMappingExpectation:
    return MemoryToHisMappingExpectation()
