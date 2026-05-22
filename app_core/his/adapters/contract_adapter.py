from __future__ import annotations

from dataclasses import dataclass
import re
import uuid

from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES, utc_now_iso

PATIENT_ID_PATTERN = r"^P-[0-9a-f]{8}$"
ENCOUNTER_ID_PATTERN = r"^E-\d{14}-[0-9a-f]{4}$"
FROZEN_CTAS_LEVELS = ("L1", "L2", "L3", "L4", "L5")
FROZEN_ZONE_VALUES = ("red", "yellow", "green")
CTAS_TO_ZONE_HINTS = {
    "L1": "red",
    "L2": "red",
    "L3": "yellow",
    "L4": "green",
    "L5": "green",
}


@dataclass(frozen=True)
class ContractFieldMapping:
    source_field: str
    contract_field: str
    notes: str


def get_contract_field_mappings() -> tuple[ContractFieldMapping, ...]:
    return (
        ContractFieldMapping(
            source_field="MemoryItem.patient_id / CurrentEncounterSummary.patient_id / HandoffMemorySnapshot.patient_id",
            contract_field="patient_id",
            notes="Must remain in the frozen P-{8 hex} format defined by A's contract freeze.",
        ),
        ContractFieldMapping(
            source_field="MemoryItem.encounter_id / CurrentEncounterSummary.encounter_id / HandoffMemorySnapshot.encounter_id",
            contract_field="encounter_id",
            notes="Must remain in the frozen E-{14 timestamp}-{4 hex} format.",
        ),
        ContractFieldMapping(
            source_field="CurrentEncounterSummary.acuity or ED triage derivation",
            contract_field="ctas_level",
            notes="Normalize to L1-L5 before any HIS-facing write or response payload.",
        ),
        ContractFieldMapping(
            source_field="CurrentEncounterSummary.current_zone or ED triage derivation",
            contract_field="zone",
            notes="Normalize to red/yellow/green for cross-team and contract use.",
        ),
        ContractFieldMapping(
            source_field="Normalized HIS write event",
            contract_field="event envelope",
            notes="Must contain event_id, event_type, occurred_at, patient_id, encounter_id, source, payload.",
        ),
    )


def normalize_contract_identifiers(*, patient_id: str, encounter_id: str, ctas_level: str, zone: str) -> dict[str, str]:
    normalized_ids = validate_contract_ids(patient_id=patient_id, encounter_id=encounter_id)
    normalized_ctas = str(ctas_level).strip().upper()
    normalized_zone = str(zone).strip().lower()
    if normalized_ctas not in FROZEN_CTAS_LEVELS:
        raise ValueError(f"ctas_level must be one of {FROZEN_CTAS_LEVELS}")
    if normalized_zone not in FROZEN_ZONE_VALUES:
        raise ValueError(f"zone must be one of {FROZEN_ZONE_VALUES}")
    return {
        **normalized_ids,
        "ctas_level": normalized_ctas,
        "zone": normalized_zone,
    }


def validate_contract_ids(*, patient_id: str, encounter_id: str) -> dict[str, str]:
    if not re.fullmatch(PATIENT_ID_PATTERN, patient_id):
        raise ValueError(f"patient_id must match {PATIENT_ID_PATTERN}")
    if not re.fullmatch(ENCOUNTER_ID_PATTERN, encounter_id):
        raise ValueError(f"encounter_id must match {ENCOUNTER_ID_PATTERN}")
    return {"patient_id": patient_id, "encounter_id": encounter_id}


def get_contract_route_names() -> tuple[str, ...]:
    return FROZEN_ROUTE_NAMES


def get_event_envelope_fields() -> tuple[str, ...]:
    return EVENT_ENVELOPE_FIELDS


def build_event_envelope(
    *,
    event_type: str,
    patient_id: str,
    encounter_id: str,
    source: str,
    payload: dict[str, object] | None = None,
    occurred_at: str | None = None,
    event_id: str | None = None,
) -> dict[str, object]:
    if not str(event_type).strip():
        raise ValueError("event_type is required")
    if not str(source).strip():
        raise ValueError("source is required")
    normalized = validate_contract_ids(patient_id=patient_id, encounter_id=encounter_id)
    envelope = {
        "event_id": event_id or f"evt-{uuid.uuid4().hex[:12]}",
        "event_type": str(event_type).strip(),
        "occurred_at": occurred_at or utc_now_iso(),
        "patient_id": normalized["patient_id"],
        "encounter_id": normalized["encounter_id"],
        "source": str(source).strip(),
        "payload": dict(payload or {}),
    }
    return {field: envelope[field] for field in EVENT_ENVELOPE_FIELDS}


def derive_zone_from_ctas(ctas_level: str) -> str:
    normalized = str(ctas_level).strip().upper()
    if normalized not in CTAS_TO_ZONE_HINTS:
        raise ValueError(f"ctas_level must be one of {FROZEN_CTAS_LEVELS}")
    return CTAS_TO_ZONE_HINTS[normalized]
