from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app_core.memory.hooks import (
    build_audit_record,
    build_handoff_snapshot_id,
    build_memory_event,
    generate_auto_encounter_id,
    generate_auto_run_id,
    next_memory_step,
)
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem
from app_core.memory.service import MemoryService, create_memory_service


class AutoMemoryHookManager:
    def __init__(
        self,
        *,
        sim_code: str,
        start_time: datetime | None = None,
        service: MemoryService | None = None,
        runtime_logger=None,
        enabled: bool | None = None,
        now: datetime | None = None,
    ) -> None:
        self.sim_code = sim_code
        self.start_time = start_time
        self.service = service or create_memory_service(enabled=enabled)
        self.runtime_logger = runtime_logger
        self.run_id = generate_auto_run_id(sim_code, now=now)
        self.mode = "auto"
        self._emitted_keys: set[tuple[str, str]] = set()
        self._active_bottlenecks: set[str] = set()
        self._memory_steps: dict[str, int] = {}
        self._registered_handlers = {
            "encounter_started": self.record_encounter_started,
            "resource_bottleneck": self.record_resource_bottlenecks,
            "boarding_timeout": self.record_boarding_timeout,
            "encounter_closed": self.record_encounter_closed,
            "disposition_decided": self.record_disposition_decided,
            "handoff_requested": self.record_handoff_requested,
            "handoff_completed": self.record_handoff_completed,
            "next_slot": self.record_next_slot,
        }

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.service, "enabled", False))

    def register_extension_event(self, event_name: str, handler) -> None:
        self._registered_handlers[str(event_name)] = handler

    def record_registered_event(self, event_name: str, *args, **kwargs):
        handler = self._registered_handlers.get(str(event_name))
        if handler is None:
            raise KeyError(f"Unknown auto memory event: {event_name}")
        return handler(*args, **kwargs)

    def sync_existing_patients(self, patients: list[Any], *, step: int, sim_time: datetime | None) -> None:
        for patient in patients:
            self.record_encounter_started(patient, step=step, sim_time=sim_time, source="seed_existing")

    def record_encounter_started(self, patient: Any, *, step: int, sim_time: datetime | None, source: str) -> dict[str, Any]:
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="encounter_started",
            source=source,
            priority="medium",
            content=f"{getattr(patient, 'name', 'Unknown patient')} entered Auto Mode flow",
            checkpoint="encounter_started",
            tags=["auto", "encounter"],
            summary_mutator=self._apply_encounter_started_summary,
            dedupe_scope="encounter_started",
            payload={
                "source": source,
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "ctas": getattr(patient.scratch, "CTAS", None),
            },
        )

    def record_boarding_timeout(self, patient: Any, *, step: int, sim_time: datetime | None) -> dict[str, Any]:
        timestamp = getattr(patient.scratch, "boarding_timeout_at", None)
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="boarding_timeout",
            source="auto_patient_runtime",
            priority="high",
            content=f"{getattr(patient, 'name', 'Unknown patient')} reached boarding timeout",
            checkpoint="boarding_timeout",
            tags=["auto", "boarding", "timeout"],
            summary_mutator=self._apply_boarding_timeout_summary,
            dedupe_scope="boarding_timeout",
            payload={
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "threshold_minutes": float(getattr(patient, "boarding_timeout_minutes", 0) or 0),
                "timestamp": timestamp.strftime("%B %d, %Y, %H:%M:%S") if timestamp else None,
                "admitted_to_hospital": bool(getattr(patient.scratch, "admitted_to_hospital", False)),
                "boarding_start": (
                    getattr(patient.scratch, "admission_boarding_start", None).strftime("%B %d, %Y, %H:%M:%S")
                    if getattr(patient.scratch, "admission_boarding_start", None)
                    else None
                ),
            },
        )

    def record_encounter_closed(
        self,
        patient: Any,
        *,
        step: int,
        sim_time: datetime | None,
        close_reason: str,
    ) -> dict[str, Any]:
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="encounter_closed",
            source="auto_runtime_cleanup",
            priority="medium",
            content=f"{getattr(patient, 'name', 'Unknown patient')} closed encounter",
            checkpoint="encounter_closed",
            tags=["auto", "closure"],
            summary_mutator=self._apply_encounter_closed_summary,
            dedupe_scope="encounter_closed",
            payload={
                "close_reason": close_reason,
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "left_without_being_seen": bool(getattr(patient.scratch, "left_without_being_seen", False)),
                "disposition_done": bool(getattr(patient.scratch, "disposition_done", False)),
                "admitted_to_hospital": bool(getattr(patient.scratch, "admitted_to_hospital", False)),
            },
        )

    def record_disposition_decided(
        self,
        patient: Any,
        *,
        step: int,
        sim_time: datetime | None,
        disposition: str,
    ) -> dict[str, Any]:
        disposition_value = str(disposition or "unknown")
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="disposition_decided",
            source="auto_patient_disposition",
            priority="high",
            content=f"{getattr(patient, 'name', 'Unknown patient')} disposition decided: {disposition_value}",
            checkpoint="doctor_assessment_checkpoint",
            tags=["auto", "disposition"],
            summary_mutator=self._apply_disposition_summary,
            dedupe_scope=f"disposition_decided:{disposition_value}",
            payload={
                "disposition": disposition_value,
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "admitted_to_hospital": bool(getattr(patient.scratch, "admitted_to_hospital", False)),
                "boarding_start": (
                    getattr(patient.scratch, "admission_boarding_start", None).strftime("%B %d, %Y, %H:%M:%S")
                    if getattr(patient.scratch, "admission_boarding_start", None)
                    else None
                ),
                "boarding_end": (
                    getattr(patient.scratch, "admission_boarding_end", None).strftime("%B %d, %Y, %H:%M:%S")
                    if getattr(patient.scratch, "admission_boarding_end", None)
                    else None
                ),
                "exit_ready_at": (
                    getattr(patient.scratch, "exit_ready_at", None).strftime("%B %d, %Y, %H:%M:%S")
                    if getattr(patient.scratch, "exit_ready_at", None)
                    else None
                ),
            },
        )

    def record_handoff_requested(
        self,
        patient: Any,
        *,
        step: int,
        sim_time: datetime | None,
        from_role: str,
        to_role: str,
        reason: str,
    ) -> dict[str, Any]:
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="handoff_requested",
            source="auto_internal_handoff",
            priority="medium",
            content=f"{getattr(patient, 'name', 'Unknown patient')} handoff requested from {from_role} to {to_role}",
            checkpoint="handoff_requested",
            tags=["auto", "handoff"],
            summary_mutator=self._apply_handoff_requested_summary,
            dedupe_scope=f"handoff_requested:{from_role}:{to_role}",
            payload={
                "from_role": from_role,
                "to_role": to_role,
                "reason": reason,
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "next_room": getattr(patient.scratch, "next_room", None),
            },
            snapshot_stage="requested",
        )

    def record_handoff_completed(
        self,
        patient: Any,
        *,
        step: int,
        sim_time: datetime | None,
        from_role: str,
        to_role: str,
        completion_note: str,
    ) -> dict[str, Any]:
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="handoff_completed",
            source="auto_internal_handoff",
            priority="medium",
            content=f"{getattr(patient, 'name', 'Unknown patient')} handoff completed from {from_role} to {to_role}",
            checkpoint="handoff_completed",
            tags=["auto", "handoff"],
            summary_mutator=self._apply_handoff_completed_summary,
            dedupe_scope=f"handoff_completed:{from_role}:{to_role}",
            payload={
                "from_role": from_role,
                "to_role": to_role,
                "completion_note": completion_note,
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "next_room": getattr(patient.scratch, "next_room", None),
            },
            snapshot_stage="completed",
        )

    def record_next_slot(
        self,
        patient: Any,
        *,
        step: int,
        sim_time: datetime | None,
        slot_name: str,
        owner_role: str,
        reason: str,
    ) -> dict[str, Any]:
        slot_value = str(slot_name or "unknown")
        return self._record_patient_event(
            patient,
            step=step,
            sim_time=sim_time,
            event_type="next_slot",
            source="auto_state_transition",
            priority="medium",
            content=f"{getattr(patient, 'name', 'Unknown patient')} next slot set to {slot_value}",
            checkpoint="next_slot",
            tags=["auto", "next_slot"],
            summary_mutator=self._apply_next_slot_summary,
            dedupe_scope=f"next_slot:{slot_value}",
            payload={
                "slot_name": slot_value,
                "owner_role": owner_role,
                "reason": reason,
                "state": getattr(patient.scratch, "state", None),
                "zone": getattr(patient.scratch, "injuries_zone", None),
                "next_room": getattr(patient.scratch, "next_room", None),
                "next_step": getattr(patient.scratch, "next_step", None),
            },
        )

    def record_resource_bottlenecks(self, server: Any, *, step: int, sim_time: datetime | None) -> list[dict[str, Any]]:
        active: dict[str, tuple[Any, dict[str, Any]]] = {}

        doctor_queue = list(getattr(server.maze, "patients_waiting_for_doctor", []))
        doctors_free = len(getattr(server.maze, "doctors_taking_more_patients", []))
        if doctor_queue and doctors_free == 0:
            patient = server.personas.get(doctor_queue[0][1])
            if patient is not None:
                active["doctor_global"] = (
                    patient,
                    {
                        "resource": "doctor_global",
                        "queue_length": len(doctor_queue),
                        "available_resources": doctors_free,
                        "capacity_hint": getattr(server, "doctor_starting_amount", None),
                    },
                )

        bedside_queue = list(server.maze.injuries_zones.get("bedside_nurse_waiting", []))
        if bedside_queue:
            patient = server.personas.get(bedside_queue[0][1])
            if patient is not None:
                active["bedside_nurse_waiting"] = (
                    patient,
                    {
                        "resource": "bedside_nurse_waiting",
                        "queue_length": len(bedside_queue),
                        "available_resources": getattr(server, "bedside_starting_amount", None),
                        "capacity_hint": getattr(server, "bedside_starting_amount", None),
                    },
                )

        results: list[dict[str, Any]] = []
        active_keys = set(active.keys())
        for resource_key, (patient, payload) in active.items():
            if resource_key in self._active_bottlenecks:
                continue
            result = self._record_patient_event(
                patient,
                step=step,
                sim_time=sim_time,
                event_type="resource_bottleneck",
                source="auto_runtime_status",
                priority="medium",
                content=f"{payload['resource']} bottleneck detected for {getattr(patient, 'name', 'Unknown patient')}",
                checkpoint="resource_bottleneck",
                tags=["auto", "resource", "queue"],
                summary_mutator=self._apply_resource_bottleneck_summary,
                dedupe_scope=f"resource_bottleneck:{resource_key}",
                payload=payload,
            )
            results.append(result)

        self._active_bottlenecks = active_keys
        return results

    def _record_patient_event(
        self,
        patient: Any,
        *,
        step: int,
        sim_time: datetime | None,
        event_type: str,
        source: str,
        priority: str | int,
        content: str,
        checkpoint: str,
        tags: list[str],
        summary_mutator,
        dedupe_scope: str,
        payload: dict[str, Any],
        snapshot_stage: str | None = None,
    ) -> dict[str, Any]:
        patient_name = getattr(patient, "name", "Unknown patient")
        encounter_id = generate_auto_encounter_id(self.run_id, patient_name)
        dedupe_key = (encounter_id, dedupe_scope)
        if dedupe_key in self._emitted_keys:
            self._log("auto memory event skipped (duplicate)", step=step, extra={"event_type": event_type, "patient": patient_name})
            return {"ok": True, "skipped": True, "duplicate": True}

        if not self.enabled:
            self._log("auto memory event skipped (disabled)", step=step, extra={"event_type": event_type, "patient": patient_name})
            return {"ok": True, "skipped": True, "disabled": True}

        memory_step = next_memory_step(self._memory_steps.get(encounter_id))
        sim_minutes = self._sim_minutes(sim_time)
        structured_facts = dict(payload)
        structured_facts["sim_time_text"] = sim_time.strftime("%B %d, %Y, %H:%M:%S") if sim_time else None
        structured_facts["memory_step"] = memory_step

        item = build_memory_event(
            run_id=self.run_id,
            mode=self.mode,
            encounter_id=encounter_id,
            patient_id=patient_name.replace(" ", "_"),
            step=int(step),
            sim_time=sim_minutes,
            agent_role="auto_runtime",
            event_type=event_type,
            source=source,
            priority=priority,
            content=content,
            structured_facts=structured_facts,
            state_before=self._build_state_snapshot(patient),
            state_after=self._build_state_snapshot(patient),
            tags=tags,
        )

        event_result = self._safe_memory_write(
            "append_event",
            checkpoint=checkpoint,
            encounter_id=encounter_id,
            action=lambda: self.service.append_event(item),
            details={"event_type": event_type, "patient": patient_name},
        )
        if not event_result.get("ok"):
            return event_result

        stored_item = event_result.get("result")
        memory_id = stored_item.memory_id if isinstance(stored_item, MemoryItem) else item.memory_id
        self._memory_steps[encounter_id] = memory_step
        self._emitted_keys.add(dedupe_key)

        summary = summary_mutator(patient, step=step, encounter_id=encounter_id, memory_id=memory_id, payload=payload)
        self._safe_memory_write(
            "update_current_summary",
            checkpoint=checkpoint,
            encounter_id=encounter_id,
            action=lambda: self.service.update_current_summary(summary),
            details={"event_type": event_type, "patient": patient_name, "memory_id": memory_id},
        )
        if snapshot_stage in {"requested", "completed"}:
            snapshot = self._build_handoff_snapshot(
                patient,
                encounter_id=encounter_id,
                memory_id=memory_id,
                payload=payload,
                stage=snapshot_stage,
                step=step,
            )
            self._safe_memory_write(
                "write_handoff_snapshot",
                checkpoint=f"handoff_{snapshot_stage}",
                encounter_id=encounter_id,
                action=lambda: self.service.write_handoff_snapshot(snapshot),
                details={"event_type": event_type, "patient": patient_name, "memory_id": memory_id},
            )
        return {"ok": True, "result": stored_item, "summary": summary}

    def _safe_memory_write(self, op_type: str, *, checkpoint: str, encounter_id: str, action, details: dict[str, Any]) -> dict[str, Any]:
        try:
            result = action()
        except Exception as exc:
            detail = dict(details)
            detail["status"] = "failed"
            detail["error"] = str(exc)
            self._safe_append_audit(encounter_id=encounter_id, op_type=op_type, checkpoint=checkpoint, details=detail)
            self._log("auto memory write failed", extra={"op_type": op_type, "checkpoint": checkpoint, "error": str(exc), **details})
            return {"ok": False, "reason": str(exc)}

        detail = dict(details)
        detail["status"] = "success"
        if hasattr(result, "memory_id"):
            detail["memory_id"] = getattr(result, "memory_id")
        self._safe_append_audit(encounter_id=encounter_id, op_type=op_type, checkpoint=checkpoint, details=detail, source_ids=[detail["memory_id"]] if "memory_id" in detail else None)
        self._log("auto memory write ok", extra={"op_type": op_type, "checkpoint": checkpoint, **details})
        return {"ok": True, "result": result}

    def _safe_append_audit(
        self,
        *,
        encounter_id: str,
        op_type: str,
        checkpoint: str,
        details: dict[str, Any],
        source_ids: list[str] | None = None,
    ) -> None:
        if not self.enabled:
            return
        try:
            record = build_audit_record(
                run_id=self.run_id,
                mode=self.mode,
                encounter_id=encounter_id,
                op_type=op_type,
                checkpoint=checkpoint,
                source_ids=source_ids,
                details=details,
            )
            self.service.append_audit(record)
        except Exception as exc:
            self._log("auto memory audit failed", extra={"op_type": op_type, "checkpoint": checkpoint, "error": str(exc)})

    def _build_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str) -> CurrentEncounterSummary:
        patient_name = getattr(patient, "name", "Unknown patient").replace(" ", "_")
        existing = self.service.get_current_summary(self.run_id, self.mode, encounter_id) if self.enabled else None
        source_ids = list(getattr(existing, "source_memory_ids", []) or [])
        if memory_id and memory_id not in source_ids:
            source_ids.append(memory_id)
        return CurrentEncounterSummary(
            run_id=self.run_id,
            mode=self.mode,
            encounter_id=encounter_id,
            patient_id=patient_name,
            current_state=str(getattr(patient.scratch, "state", "UNKNOWN") or "UNKNOWN"),
            current_zone=getattr(patient.scratch, "injuries_zone", None),
            acuity=str(getattr(patient.scratch, "CTAS", "")) if getattr(patient.scratch, "CTAS", None) is not None else None,
            latest_vitals=dict(getattr(existing, "latest_vitals", {}) or {}),
            active_risks=list(getattr(existing, "active_risks", []) or []),
            pending_tasks=list(getattr(existing, "pending_tasks", []) or []),
            completed_actions=list(getattr(existing, "completed_actions", []) or []),
            latest_doctor_findings=dict(getattr(existing, "latest_doctor_findings", {}) or {}),
            latest_test_status=dict(getattr(existing, "latest_test_status", {}) or {}),
            source_memory_ids=source_ids,
            updated_at_step=int(step),
        )

    def _apply_encounter_started_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        summary.pending_tasks.append({"task": "triage_or_wait", "source": payload.get("source")})
        summary.completed_actions.append({"event": "encounter_started", "step": int(step)})
        return summary

    def _apply_boarding_timeout_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        summary.active_risks.append({
            "risk": "boarding_timeout",
            "timestamp": payload.get("timestamp"),
            "threshold_minutes": payload.get("threshold_minutes"),
        })
        summary.latest_test_status["latest_timeout"] = payload
        summary.completed_actions.append({"event": "boarding_timeout", "step": int(step)})
        return summary

    def _apply_encounter_closed_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        object.__setattr__(summary, "current_state", "CLOSED")
        summary.latest_doctor_findings["closure"] = payload
        summary.completed_actions.append({"event": "encounter_closed", "step": int(step), "reason": payload.get("close_reason")})
        object.__setattr__(summary, "pending_tasks", [])
        return summary

    def _apply_resource_bottleneck_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        summary.pending_tasks.append({
            "task": "wait_for_resource",
            "resource": payload.get("resource"),
            "queue_length": payload.get("queue_length"),
        })
        summary.active_risks.append({
            "risk": "resource_bottleneck",
            "resource": payload.get("resource"),
        })
        return summary

    def _apply_disposition_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        summary.latest_doctor_findings["disposition"] = payload
        summary.completed_actions.append({"event": "disposition_decided", "step": int(step), "disposition": payload.get("disposition")})
        return summary

    def _apply_handoff_requested_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        summary.pending_tasks.append({
            "task": "handoff_requested",
            "from_role": payload.get("from_role"),
            "to_role": payload.get("to_role"),
            "reason": payload.get("reason"),
        })
        summary.completed_actions.append({"event": "handoff_requested", "step": int(step)})
        return summary

    def _apply_handoff_completed_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        object.__setattr__(summary, "pending_tasks", [
            task for task in summary.pending_tasks
            if task.get("task") != "handoff_requested"
        ])
        summary.completed_actions.append({"event": "handoff_completed", "step": int(step)})
        summary.latest_doctor_findings["latest_handoff"] = payload
        return summary

    def _apply_next_slot_summary(self, patient: Any, *, step: int, encounter_id: str, memory_id: str, payload: dict[str, Any]) -> CurrentEncounterSummary:
        summary = self._build_summary(patient, step=step, encounter_id=encounter_id, memory_id=memory_id)
        summary.latest_doctor_findings["next_slot"] = payload
        summary.pending_tasks.append({
            "task": "next_slot",
            "slot_name": payload.get("slot_name"),
            "owner_role": payload.get("owner_role"),
        })
        return summary

    def _build_handoff_snapshot(
        self,
        patient: Any,
        *,
        encounter_id: str,
        memory_id: str,
        payload: dict[str, Any],
        stage: str,
        step: int,
    ) -> HandoffMemorySnapshot:
        patient_name = getattr(patient, "name", "Unknown patient").replace(" ", "_")
        snapshot_id = build_handoff_snapshot_id(self.run_id, encounter_id, stage)
        return HandoffMemorySnapshot(
            snapshot_id=snapshot_id,
            run_id=self.run_id,
            mode=self.mode,
            encounter_id=encounter_id,
            patient_id=patient_name,
            from_role=str(payload.get("from_role") or "unknown"),
            to_role=str(payload.get("to_role") or "unknown"),
            handoff_stage=stage,
            patient_brief=str(payload.get("reason") or payload.get("completion_note") or f"{patient_name} handoff"),
            current_state=self._build_state_snapshot(patient),
            pending_tasks=[{"task": "handoff", "stage": stage}],
            source_memory_ids=[memory_id],
            created_at_step=int(step),
        )

    def _build_state_snapshot(self, patient: Any) -> dict[str, Any]:
        scratch = getattr(patient, "scratch", None)
        if scratch is None:
            return {}
        return {
            "state": getattr(scratch, "state", None),
            "zone": getattr(scratch, "injuries_zone", None),
            "ctas": getattr(scratch, "CTAS", None),
            "assigned_doctor": getattr(scratch, "assigned_doctor", None),
            "testing_kind": getattr(scratch, "testing_kind", None),
            "bed_assignment": getattr(scratch, "bed_assignment", None),
            "disposition_done": getattr(scratch, "disposition_done", None),
        }

    def _sim_minutes(self, sim_time: datetime | None) -> float | None:
        if sim_time is None or self.start_time is None:
            return None
        return max(0.0, (sim_time - self.start_time).total_seconds() / 60.0)

    def _log(self, message: str, *, step: int | None = None, extra: dict[str, Any] | None = None) -> None:
        if self.runtime_logger is None:
            return
        try:
            self.runtime_logger(message, step=step, extra=extra)
        except Exception:
            return
