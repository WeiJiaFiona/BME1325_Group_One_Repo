from __future__ import annotations

from dataclasses import dataclass
import uuid

from app_core.his.adapters.contract_adapter import build_event_envelope, derive_zone_from_ctas
from app_core.his.schemas import (
    ClinicalDocumentRecord,
    CurrentSummaryRecord,
    DocumentRegistryEntry,
    EventRegistryEntry,
    HandoffSnapshotRecord,
)
from app_core.his.services.document_registry_service import register_document
from app_core.his.services.encounter_service import write_current_summary
from app_core.his.services.event_registry_service import append_event_registry_entry
from app_core.his.services.handoff_service import write_handoff_snapshot
from app_core.his.storage.base import HisStorage
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
    payload: dict[str, object] | None = None


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
    raw_payload = {
        "memory_id": item.memory_id,
        "run_id": item.run_id,
        "mode": item.mode,
        "encounter_id": item.encounter_id,
        "patient_id": item.patient_id,
        "step": item.step,
        "sim_time": item.sim_time,
        "wall_time": item.wall_time,
        "agent_role": item.agent_role,
        "event_type": item.event_type,
        "source": item.source,
        "priority": item.priority,
        "content": item.content,
        "structured_facts": item.structured_facts,
        "state_before": item.state_before,
        "state_after": item.state_after,
        "tags": item.tags,
        "salience": item.salience,
        "retrieval_scope": item.retrieval_scope,
        "created_at": item.created_at,
    }
    envelope = build_event_envelope(
        event_type=item.event_type,
        patient_id=item.patient_id,
        encounter_id=item.encounter_id,
        source=item.source,
        payload={
            "memory_id": item.memory_id,
            "step": item.step,
            "agent_role": item.agent_role,
            "content": item.content,
            "structured_facts": item.structured_facts,
            "priority": item.priority,
            "tags": item.tags,
        },
        occurred_at=item.created_at,
        event_id=f"evt-{item.memory_id}",
    )
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
            payload=raw_payload,
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
            payload=envelope,
        ),
    )


def map_current_summary_to_his_write(summary: CurrentEncounterSummary) -> PendingHisWritePlan:
    ctas_level = f"L{summary.acuity}" if str(summary.acuity or "").isdigit() else None
    payload = {
        "run_id": summary.run_id,
        "mode": summary.mode,
        "current_zone": summary.current_zone or (derive_zone_from_ctas(ctas_level) if ctas_level else None),
        "acuity": summary.acuity,
        "latest_vitals": summary.latest_vitals,
        "active_risks": summary.active_risks,
        "pending_tasks": summary.pending_tasks,
        "completed_actions": summary.completed_actions,
        "latest_doctor_findings": summary.latest_doctor_findings,
        "latest_test_status": summary.latest_test_status,
    }
    return PendingHisWritePlan(
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
        payload={
            "summary_id": f"summary-{summary.encounter_id}",
            "patient_id": summary.patient_id,
            "encounter_id": summary.encounter_id,
            "current_state": summary.current_state,
            "payload": payload,
            "source_memory_ids": [{"memory_id": item} for item in summary.source_memory_ids],
            "updated_at": summary.updated_at_step,
        },
    )


def map_handoff_snapshot_to_his_writes(snapshot: HandoffMemorySnapshot) -> tuple[PendingHisWritePlan, ...]:
    document_id = f"doc-{snapshot.snapshot_id}"
    return (
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
            payload={
                "snapshot_id": snapshot.snapshot_id,
                "patient_id": snapshot.patient_id,
                "encounter_id": snapshot.encounter_id,
                "from_role": snapshot.from_role,
                "to_role": snapshot.to_role,
                "handoff_stage": snapshot.handoff_stage,
                "patient_brief": snapshot.patient_brief,
                "current_state": snapshot.current_state,
                "completed_actions": snapshot.completed_actions,
                "pending_tasks": snapshot.pending_tasks,
                "active_risks": snapshot.active_risks,
                "next_actions": snapshot.next_actions,
                "created_at": snapshot.created_at_step,
            },
        ),
        PendingHisWritePlan(
            target_table="clinical_documents",
            service_entrypoint="app_core.his.services.document_registry_service.register_document",
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
            payload={
                "document_id": document_id,
                "registry_id": f"reg-{snapshot.snapshot_id}",
                "patient_id": snapshot.patient_id,
                "encounter_id": snapshot.encounter_id,
                "document_type": "handoff_snapshot",
                "content": {
                    "patient_brief": snapshot.patient_brief,
                    "current_state": snapshot.current_state,
                    "completed_actions": snapshot.completed_actions,
                    "pending_tasks": snapshot.pending_tasks,
                    "active_risks": snapshot.active_risks,
                    "next_actions": snapshot.next_actions,
                    "source_memory_ids": snapshot.source_memory_ids,
                },
                "metadata": {
                    "snapshot_id": snapshot.snapshot_id,
                    "handoff_stage": snapshot.handoff_stage,
                    "from_role": snapshot.from_role,
                    "to_role": snapshot.to_role,
                },
            },
        ),
    )


def build_timeline_export_plan(*, encounter_id: str, patient_id: str) -> PendingHisWritePlan:
    return PendingHisWritePlan(
        target_table="replay_exports",
        service_entrypoint="app_core.his.query.timeline_export",
        required_fields=("patient_id", "encounter_id", "events", "summaries", "snapshots", "audits"),
        notes="Assemble one encounter-scoped replay bundle from already persisted HIS artifacts.",
        payload={"patient_id": patient_id, "encounter_id": encounter_id},
    )


def persist_memory_item(item: MemoryItem, *, storage: HisStorage) -> tuple[dict[str, object], EventRegistryEntry]:
    plans = map_memory_item_to_his_writes(item)
    envelope = plans[1].payload or {}
    entry = EventRegistryEntry(
        event_id=str(envelope["event_id"]),
        event_type=str(envelope["event_type"]),
        occurred_at=str(envelope["occurred_at"]),
        patient_id=str(envelope["patient_id"]),
        encounter_id=str(envelope["encounter_id"]),
        source=str(envelope["source"]),
        payload=dict(envelope["payload"]),
        tags=list(item.tags),
    )
    stored = append_event_registry_entry(entry, storage=storage)
    return dict(plans[0].payload or {}), stored


def persist_current_summary(summary: CurrentEncounterSummary, *, storage: HisStorage) -> CurrentSummaryRecord:
    plan = map_current_summary_to_his_write(summary)
    payload = dict(plan.payload or {})
    record = CurrentSummaryRecord(
        encounter_id=str(payload["encounter_id"]),
        patient_id=str(payload["patient_id"]),
        summary_id=str(payload["summary_id"]),
        current_state=str(payload["current_state"]),
        payload=dict(payload["payload"]),
        source_memory_ids=list(payload.get("source_memory_ids", [])),
        updated_at=str(payload["updated_at"]),
    )
    return write_current_summary(record, storage=storage)


def persist_handoff_snapshot(
    snapshot: HandoffMemorySnapshot,
    *,
    storage: HisStorage,
) -> tuple[HandoffSnapshotRecord, ClinicalDocumentRecord, DocumentRegistryEntry]:
    handoff_plan, document_plan = map_handoff_snapshot_to_his_writes(snapshot)
    handoff_payload = dict(handoff_plan.payload or {})
    handoff_record = HandoffSnapshotRecord(
        snapshot_id=str(handoff_payload["snapshot_id"]),
        encounter_id=str(handoff_payload["encounter_id"]),
        patient_id=str(handoff_payload["patient_id"]),
        from_role=str(handoff_payload["from_role"]),
        to_role=str(handoff_payload["to_role"]),
        handoff_stage=str(handoff_payload["handoff_stage"]),
        patient_brief=str(handoff_payload["patient_brief"]),
        current_state=dict(handoff_payload["current_state"]),
        completed_actions=list(handoff_payload["completed_actions"]),
        pending_tasks=list(handoff_payload["pending_tasks"]),
        active_risks=list(handoff_payload["active_risks"]),
        next_actions=list(handoff_payload["next_actions"]),
        created_at=str(handoff_payload["created_at"]),
    )
    stored_handoff = write_handoff_snapshot(handoff_record, storage=storage)

    document_payload = dict(document_plan.payload or {})
    document = ClinicalDocumentRecord(
        document_id=str(document_payload["document_id"]),
        encounter_id=str(document_payload["encounter_id"]),
        patient_id=str(document_payload["patient_id"]),
        document_type=str(document_payload["document_type"]),
        content=dict(document_payload["content"]),
    )
    registry_entry = DocumentRegistryEntry(
        registry_id=str(document_payload["registry_id"]),
        document_id=document.document_id,
        encounter_id=document.encounter_id,
        patient_id=document.patient_id,
        document_type=document.document_type,
        metadata=dict(document_payload["metadata"]),
    )
    stored_document, stored_registry = register_document(document, registry_entry=registry_entry, storage=storage)
    if stored_registry is None:
        raise RuntimeError("Document registry write unexpectedly returned None")
    return stored_handoff, stored_document, stored_registry
