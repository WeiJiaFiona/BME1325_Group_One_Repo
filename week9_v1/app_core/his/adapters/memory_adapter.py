from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid

from app_core.his.adapters.contract_adapter import (
    build_event_envelope_placeholder,
    normalize_contract_identifiers,
    normalize_ctas_level,
    normalize_zone,
)
from app_core.his.config import utc_now_iso
from app_core.his.schemas import ClinicalDocumentRecord, CurrentSummaryRecord, DocumentRegistryEntry, EventRegistryEntry, HandoffSnapshotRecord
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
    payload: dict[str, Any] = field(default_factory=dict)


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
            notes="Mirror the handoff snapshot into the HIS document-facing surface.",
        ),
        PendingHisWritePlan(
            target_table="replay_exports",
            service_entrypoint="app_core.his.services.document_registry_service.register_document",
            required_fields=("patient_id", "encounter_id", "events", "summaries", "snapshots", "audits"),
            notes="Emit replay/timeline bundles as HIS-side documents until A adds a dedicated replay export table.",
        ),
    )


def _summary_payload(summary: CurrentEncounterSummary) -> dict[str, Any]:
    ctas_level = normalize_ctas_level(summary.acuity or "L3")
    zone = normalize_zone(summary.current_zone, ctas_level)
    return {
        "run_id": summary.run_id,
        "mode": summary.mode,
        "ctas_level": ctas_level,
        "zone": zone,
        "latest_vitals": dict(summary.latest_vitals),
        "active_risks": list(summary.active_risks),
        "pending_tasks": list(summary.pending_tasks),
        "completed_actions": list(summary.completed_actions),
        "latest_doctor_findings": dict(summary.latest_doctor_findings),
        "latest_test_status": dict(summary.latest_test_status),
        "source_memory_ids": list(summary.source_memory_ids),
        "updated_at_step": summary.updated_at_step,
    }


def map_memory_item_to_his_writes(item: MemoryItem) -> tuple[PendingHisWritePlan, ...]:
    normalized = normalize_contract_identifiers(
        patient_id=item.patient_id,
        encounter_id=item.encounter_id,
        ctas_level="L3",
        zone="yellow",
    )
    raw_memory_payload = item.to_dict()
    envelope = build_event_envelope_placeholder(
        event_type=item.event_type,
        patient_id=normalized["patient_id"],
        encounter_id=normalized["encounter_id"],
        source=item.source,
        payload={
            "memory_id": item.memory_id,
            "step": item.step,
            "mode": item.mode,
            "agent_role": item.agent_role,
            "priority": item.priority,
            "content": item.content,
            "structured_facts": item.structured_facts,
            "state_before": item.state_before,
            "state_after": item.state_after,
            "tags": item.tags,
            "memory_event": raw_memory_payload,
        },
        occurred_at=item.wall_time or item.created_at,
        event_id=f"evt-{item.memory_id}",
    )
    return (
        PendingHisWritePlan(
            target_table="memory_events",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[0],
            required_fields=tuple(raw_memory_payload.keys()),
            notes="Raw MemoryItem payload mirrored inside the event envelope payload.",
            payload=raw_memory_payload,
        ),
        PendingHisWritePlan(
            target_table="event_registry",
            service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[0],
            required_fields=EVENT_REGISTRY_FIELDS,
            notes="Normalized HIS event envelope for formal event replay and downstream integrations.",
            payload=envelope,
        ),
    )


EVENT_REGISTRY_FIELDS = (
    "event_id",
    "event_type",
    "occurred_at",
    "patient_id",
    "encounter_id",
    "source",
    "payload",
)


def persist_memory_item_to_his(item: MemoryItem, *, storage: HisStorage) -> EventRegistryEntry:
    event_plan = map_memory_item_to_his_writes(item)[1]
    return append_event_registry_entry(EventRegistryEntry(**event_plan.payload), storage=storage)


def map_current_summary_to_his_write(summary: CurrentEncounterSummary) -> PendingHisWritePlan:
    payload = _summary_payload(summary)
    normalized = normalize_contract_identifiers(
        patient_id=summary.patient_id,
        encounter_id=summary.encounter_id,
        ctas_level=payload["ctas_level"],
        zone=payload["zone"],
    )
    summary_id = f"sum-{summary.encounter_id}"
    summary_payload = {
        "summary_id": summary_id,
        "patient_id": normalized["patient_id"],
        "encounter_id": normalized["encounter_id"],
        "current_state": summary.current_state,
        "payload": payload,
        "updated_at": payload["updated_at_step"],
    }
    return PendingHisWritePlan(
        target_table="current_encounter_summaries",
        service_entrypoint=FROZEN_MEMORY_SERVICE_ENTRYPOINTS[1],
        required_fields=("summary_id", "patient_id", "encounter_id", "current_state", "payload", "updated_at"),
        notes="Current encounter summary projection persisted through A's encounter service.",
        payload=summary_payload,
    )


def persist_current_summary_to_his(summary: CurrentEncounterSummary, *, storage: HisStorage) -> CurrentSummaryRecord:
    plan = map_current_summary_to_his_write(summary)
    record = CurrentSummaryRecord(
        encounter_id=plan.payload["encounter_id"],
        patient_id=plan.payload["patient_id"],
        summary_id=plan.payload["summary_id"],
        current_state=plan.payload["current_state"],
        payload=plan.payload["payload"],
        source_memory_ids=[{"memory_id": memory_id} for memory_id in summary.source_memory_ids],
    )
    return write_current_summary(record, storage=storage)


def map_handoff_snapshot_to_his_writes(snapshot: HandoffMemorySnapshot) -> tuple[PendingHisWritePlan, ...]:
    current_state = dict(snapshot.current_state)
    ctas_level = normalize_ctas_level(
        current_state.get("ctas_level")
        or current_state.get("acuity")
        or current_state.get("ctas_compat")
        or "L3"
    )
    zone = normalize_zone(current_state.get("zone"), ctas_level)
    normalized = normalize_contract_identifiers(
        patient_id=snapshot.patient_id,
        encounter_id=snapshot.encounter_id,
        ctas_level=ctas_level,
        zone=zone,
    )
    structured_snapshot = {
        "snapshot_id": snapshot.snapshot_id,
        "patient_id": normalized["patient_id"],
        "encounter_id": normalized["encounter_id"],
        "from_role": snapshot.from_role,
        "to_role": snapshot.to_role,
        "handoff_stage": snapshot.handoff_stage,
        "patient_brief": snapshot.patient_brief,
        "current_state": {
            **current_state,
            "ctas_level": ctas_level,
            "zone": zone,
        },
        "completed_actions": list(snapshot.completed_actions),
        "pending_tasks": list(snapshot.pending_tasks),
        "active_risks": list(snapshot.active_risks),
        "next_actions": list(snapshot.next_actions),
        "created_at": utc_now_iso(),
    }
    clinical_document_payload = {
        "document_id": f"doc-{snapshot.snapshot_id}",
        "registry_id": f"docreg-{snapshot.snapshot_id}",
        "document_type": f"handoff_{snapshot.handoff_stage}",
        "content": {
            "patient_brief": snapshot.patient_brief,
            "current_state": structured_snapshot["current_state"],
            "completed_actions": list(snapshot.completed_actions),
            "pending_tasks": list(snapshot.pending_tasks),
            "active_risks": list(snapshot.active_risks),
            "next_actions": list(snapshot.next_actions),
            "source_memory_ids": list(snapshot.source_memory_ids),
        },
    }
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
                "completed_actions",
                "pending_tasks",
                "active_risks",
                "next_actions",
            ),
            notes="Structured HIS handoff continuity artifact.",
            payload=structured_snapshot,
        ),
        PendingHisWritePlan(
            target_table="clinical_documents",
            service_entrypoint="app_core.his.services.document_registry_service.register_document",
            required_fields=("document_id", "registry_id", "document_type", "content"),
            notes="Readable HIS-facing handoff document mirrored from the structured snapshot.",
            payload=clinical_document_payload,
        ),
    )


def persist_handoff_snapshot_to_his(
    snapshot: HandoffMemorySnapshot,
    *,
    storage: HisStorage,
) -> tuple[HandoffSnapshotRecord, ClinicalDocumentRecord, DocumentRegistryEntry]:
    handoff_plan, document_plan = map_handoff_snapshot_to_his_writes(snapshot)
    stored_snapshot = write_handoff_snapshot(HandoffSnapshotRecord(**handoff_plan.payload), storage=storage)
    stored_document, stored_registry = register_document(
        ClinicalDocumentRecord(
            document_id=document_plan.payload["document_id"],
            encounter_id=snapshot.encounter_id,
            patient_id=snapshot.patient_id,
            document_type=document_plan.payload["document_type"],
            content=document_plan.payload["content"],
        ),
        registry_entry=DocumentRegistryEntry(
            registry_id=document_plan.payload["registry_id"],
            document_id=document_plan.payload["document_id"],
            encounter_id=snapshot.encounter_id,
            patient_id=snapshot.patient_id,
            document_type=document_plan.payload["document_type"],
            metadata={"snapshot_id": snapshot.snapshot_id},
        ),
        storage=storage,
    )
    if stored_registry is None:
        raise RuntimeError("Document registry entry was not created for handoff snapshot")
    return stored_snapshot, stored_document, stored_registry


def build_timeline_export_placeholder(*, encounter_id: str, patient_id: str) -> PendingHisWritePlan:
    return PendingHisWritePlan(
        target_table="replay_exports",
        service_entrypoint="app_core.his.services.document_registry_service.register_document",
        required_fields=("patient_id", "encounter_id", "events", "summaries", "snapshots", "audits"),
        notes="Runtime timeline exports are mirrored into clinical_documents until replay_exports receives a first-class service.",
        payload={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "document_type": "timeline_export",
        },
    )


def write_timeline_export_document(
    *,
    encounter_id: str,
    patient_id: str,
    bundle: dict[str, Any],
    storage: HisStorage,
) -> tuple[ClinicalDocumentRecord, DocumentRegistryEntry]:
    doc_id = f"doc-timeline-{uuid.uuid4().hex[:12]}"
    registry_id = f"docreg-timeline-{uuid.uuid4().hex[:12]}"
    document, registry = register_document(
        ClinicalDocumentRecord(
            document_id=doc_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
            document_type="timeline_export",
            content=bundle,
        ),
        registry_entry=DocumentRegistryEntry(
            registry_id=registry_id,
            document_id=doc_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
            document_type="timeline_export",
            metadata={"bundle_keys": sorted(bundle.keys())},
        ),
        storage=storage,
    )
    if registry is None:
        raise RuntimeError("Timeline export document registry entry was not created")
    return document, registry
