from __future__ import annotations

from dataclasses import dataclass

from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem

FROZEN_MEMORY_SERVICE_ENTRYPOINTS = (
    "app_core.his.services.event_registry_service.append_event_registry_entry",
    "app_core.his.services.encounter_service.write_current_summary",
    "app_core.his.services.handoff_service.write_handoff_snapshot",
)


@dataclass(frozen=True)
class PendingHisWritePlan:
    target_table: str
    service_entrypoint: str
    required_fields: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class MemoryToHisMappingExpectation:
    memory_event_target: tuple[str, ...] = ("memory_events", "event_registry")
    current_summary_target: tuple[str, ...] = ("current_encounter_summaries",)
    handoff_snapshot_target: tuple[str, ...] = ("handoff_snapshots", "clinical_documents")
    replay_export_target: tuple[str, ...] = ("replay_exports",)
    accepted_inputs: tuple[type[object], ...] = (
        MemoryItem,
        CurrentEncounterSummary,
        HandoffMemorySnapshot,
    )


def get_memory_to_his_mapping_expectation() -> MemoryToHisMappingExpectation:
    return MemoryToHisMappingExpectation()


def get_memory_upgrade_plan() -> tuple[PendingHisWritePlan, ...]:
    return (
        PendingHisWritePlan(
            target_table="memory_events",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[0],
            required_fields=(
                "memory_id",
                "patient_id",
                "encounter_id",
                "step",
                "event_type",
                "source",
                "content",
                "structured_facts",
                "created_at",
            ),
            notes="Persist the raw MemoryItem as the HIS-side event timeline source of truth.",
        ),
        PendingHisWritePlan(
            target_table="event_registry",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[0],
            required_fields=(
                "event_id",
                "event_type",
                "occurred_at",
                "patient_id",
                "encounter_id",
                "source",
                "payload",
            ),
            notes="Publish a normalized HIS event envelope alongside the raw memory event write.",
        ),
        PendingHisWritePlan(
            target_table="current_encounter_summaries",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[1],
            required_fields=(
                "summary_id",
                "patient_id",
                "encounter_id",
                "current_state",
                "payload",
                "updated_at",
            ),
            notes="Project CurrentEncounterSummary into the HIS read model without bypassing the service layer.",
        ),
        PendingHisWritePlan(
            target_table="handoff_snapshots",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[2],
            required_fields=(
                "snapshot_id",
                "patient_id",
                "encounter_id",
                "from_role",
                "to_role",
                "handoff_stage",
                "patient_brief",
                "current_state",
                "created_at",
            ),
            notes="Persist the structured handoff payload for queryable HIS-side continuity.",
        ),
        PendingHisWritePlan(
            target_table="clinical_documents",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[2],
            required_fields=(
                "snapshot_id",
                "patient_id",
                "encounter_id",
                "patient_brief",
                "completed_actions",
                "pending_tasks",
                "active_risks",
                "next_actions",
            ),
            notes="Mirror the handoff snapshot into the HIS document-facing surface when A exposes the document write path.",
        ),
        PendingHisWritePlan(
            target_table="replay_exports",
            service_entrypoint="TODO: freeze replay export service entrypoint with Developer A",
            required_fields=("patient_id", "encounter_id", "events", "summaries", "snapshots", "audits"),
            notes="Reserve a non-runtime placeholder for timeline export bundles and QA replay artifacts.",
        ),
    )


def map_memory_item_to_his_writes(item: MemoryItem) -> tuple[PendingHisWritePlan, ...]:
    # The implementation must stay behind A's official service boundary and reuse
    # the frozen event envelope. Do not write SQL or storage calls from this adapter.
    raise NotImplementedError(
        "TODO: after app_core.his.storage.base and service wiring are available, "
        "translate MemoryItem into memory_events + event_registry writes."
    )


def map_current_summary_to_his_write(summary: CurrentEncounterSummary) -> PendingHisWritePlan:
    # This function should eventually build the payload for
    # encounter_service.write_current_summary(...) only.
    raise NotImplementedError(
        "TODO: map CurrentEncounterSummary into current_encounter_summaries via "
        "encounter_service.write_current_summary."
    )


def map_handoff_snapshot_to_his_writes(snapshot: HandoffMemorySnapshot) -> tuple[PendingHisWritePlan, ...]:
    # This must fan out through A's handoff/document service boundary when the
    # document registry write path is frozen.
    raise NotImplementedError(
        "TODO: map HandoffMemorySnapshot into handoff_snapshots and clinical_documents "
        "without bypassing handoff/document services."
    )


def build_timeline_export_placeholder(*, encounter_id: str, patient_id: str) -> PendingHisWritePlan:
    # Timeline export remains scaffold-only until A exposes the storage/service
    # path for replay_exports and B wires the summary/handoff joins.
    raise NotImplementedError(
        "TODO: build replay_exports payloads once the HIS replay/timeline boundary is frozen."
    )
