from __future__ import annotations

import bisect
from typing import Any


def patient_name_in_queue(queue: list[Any], patient_name: str) -> bool:
    return any(isinstance(entry, (list, tuple)) and len(entry) >= 2 and str(entry[1]) == str(patient_name) for entry in queue)


def patient_has_bedside_reinsert_evidence(patient: Any) -> bool:
    scratch = getattr(patient, "scratch", None)
    if scratch is None:
        return False
    return (
        getattr(scratch, "ed_arrival_minute", None) is not None
        and getattr(scratch, "triage_completed_minute", None) is not None
    )


def _patient_record(data_collection: dict[str, Any] | None, patient_name: str) -> dict[str, Any] | None:
    if not isinstance(data_collection, dict):
        return None
    patient_bucket = data_collection.setdefault("Patient", {})
    if not isinstance(patient_bucket, dict):
        return None
    record = patient_bucket.setdefault(patient_name, {})
    return record if isinstance(record, dict) else None


def guarded_bedside_reinsert(
    *,
    queue: list[Any],
    patient: Any,
    priority: int | float,
    data_collection: dict[str, Any] | None = None,
    max_reinsert_count: int = 3,
) -> tuple[bool, str]:
    patient_name = str(getattr(patient, "name", ""))
    if not patient_name:
        return False, "missing_patient_name"
    if patient_name_in_queue(queue, patient_name):
        return False, "already_in_bedside_nurse_waiting"
    if not patient_has_bedside_reinsert_evidence(patient):
        return False, "missing_arrival_or_triage_evidence"

    scratch = getattr(patient, "scratch", None)
    current_count = int(getattr(scratch, "bedside_reinsert_count", 0) or 0)
    next_count = current_count + 1
    setattr(scratch, "bedside_reinsert_count", next_count)
    record = _patient_record(data_collection, patient_name)
    if record is not None:
        record["bedside_reinsert_count"] = next_count
    if next_count > int(max_reinsert_count):
        if not getattr(scratch, "bedside_reinsert_warning_emitted", False):
            setattr(scratch, "bedside_reinsert_warning_emitted", True)
            return False, "reinsert_count_exceeded_warning"
        return False, "reinsert_count_exceeded"

    bisect.insort_right(queue, [priority, patient_name])
    return True, "inserted"


def select_bedside_patient_for_assignment(
    *,
    queue: list[Any],
    personas: dict[str, Any],
    zone_has_space,
    reserve_bed,
    assigned_patient_ids_this_step: set[str],
    bed_tracked_zones: set[str] | None = None,
) -> tuple[Any | None, Any | None, Any | None]:
    bed_tracked_zones = bed_tracked_zones or set()
    selected_patient = None
    selected_entry = None
    reserved_bed = None
    for entry in list(queue):
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            try:
                queue.remove(entry)
            except ValueError:
                pass
            continue
        patient_name = str(entry[1])
        curr_persona = personas.get(patient_name)
        if not curr_persona:
            queue.remove(entry)
            continue
        zone = getattr(curr_persona.scratch, "next_room", None)
        if not zone:
            queue.remove(entry)
            continue
        if curr_persona.scratch.state not in {"WAITING_FOR_NURSE", "WAITING_FOR_TEST"}:
            queue.remove(entry)
            continue
        if patient_name in assigned_patient_ids_this_step:
            continue
        if selected_patient is None and zone_has_space(zone):
            reserved_bed = reserve_bed(curr_persona, zone)
            if zone in bed_tracked_zones and not reserved_bed:
                continue
            selected_patient = curr_persona
            selected_entry = entry
            queue.remove(entry)
            assigned_patient_ids_this_step.add(patient_name)
            continue
        if entry[0] > 3:
            entry[0] -= 1
    return selected_patient, selected_entry, reserved_bed
