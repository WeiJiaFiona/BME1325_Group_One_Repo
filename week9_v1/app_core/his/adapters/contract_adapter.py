from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
import uuid

from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES, utc_now_iso

PATIENT_ID_PATTERN = r"^P-[0-9a-f]{8}$"
ENCOUNTER_ID_PATTERN = r"^E-\d{14}-[0-9a-f]{4}$"
FROZEN_CTAS_LEVELS = ("L1", "L2", "L3", "L4", "L5")
FROZEN_ZONE_VALUES = ("red", "orange", "yellow", "green", "blue")
CTAS_TO_ZONE_HINTS = {
    "L1": "red",
    "L2": "orange",
    "L3": "yellow",
    "L4": "green",
    "L5": "blue",
}
_ACUITY_TO_CTAS = {
    "A": "L1",
    "B": "L2",
    "C": "L3",
    "D": "L4",
}
_ZONE_ALIASES = {
    "resus": "red",
    "resuscitation": "red",
    "orange_zone": "orange",
    "yellow_zone": "yellow",
    "green_zone": "green",
    "blue_zone": "blue",
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
            notes="Normalize to red/orange/yellow/green/blue for cross-team and contract use.",
        ),
        ContractFieldMapping(
            source_field="Normalized HIS write event",
            contract_field="event envelope",
            notes="Must contain event_id, event_type, occurred_at, patient_id, encounter_id, source, payload.",
        ),
    )


def normalize_ctas_level(raw_value: str | int | None) -> str:
    if raw_value is None:
        raise ValueError("ctas_level is required")
    if isinstance(raw_value, int):
        label = f"L{raw_value}"
    else:
        cleaned = str(raw_value).strip().upper()
        if not cleaned:
            raise ValueError("ctas_level cannot be empty")
        if cleaned in FROZEN_CTAS_LEVELS:
            label = cleaned
        elif cleaned.isdigit():
            label = f"L{cleaned}"
        elif cleaned in _ACUITY_TO_CTAS:
            label = _ACUITY_TO_CTAS[cleaned]
        elif cleaned.startswith("CTAS"):
            label = f"L{cleaned.removeprefix('CTAS').strip()}"
        else:
            raise ValueError(f"Unsupported CTAS value: {raw_value}")
    if label not in FROZEN_CTAS_LEVELS:
        raise ValueError(f"Unsupported normalized CTAS value: {label}")
    return label


def derive_zone_from_ctas(ctas_level: str) -> str:
    normalized_ctas = normalize_ctas_level(ctas_level)
    return CTAS_TO_ZONE_HINTS[normalized_ctas]


def normalize_zone(zone: str | None, ctas_level: str) -> str:
    if zone is None or not str(zone).strip():
        return derive_zone_from_ctas(ctas_level)
    cleaned = str(zone).strip().lower().replace("-", "_").replace(" ", "_")
    cleaned = _ZONE_ALIASES.get(cleaned, cleaned)
    if cleaned not in FROZEN_ZONE_VALUES:
        return derive_zone_from_ctas(ctas_level)
    return cleaned


def normalize_contract_identifiers(*, patient_id: str, encounter_id: str, ctas_level: str, zone: str) -> dict[str, str]:
    normalized_ctas = normalize_ctas_level(ctas_level)
    normalized_zone = normalize_zone(zone, normalized_ctas)
    if not re.fullmatch(PATIENT_ID_PATTERN, patient_id):
        raise ValueError(f"patient_id does not match contract freeze: {patient_id}")
    if not re.fullmatch(ENCOUNTER_ID_PATTERN, encounter_id):
        raise ValueError(f"encounter_id does not match contract freeze: {encounter_id}")
    return {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ctas_level": normalized_ctas,
        "zone": normalized_zone,
    }


def get_contract_route_names() -> tuple[str, ...]:
    return FROZEN_ROUTE_NAMES


def get_event_envelope_fields() -> tuple[str, ...]:
    return EVENT_ENVELOPE_FIELDS


def build_event_envelope_placeholder(
    *,
    event_type: str,
    patient_id: str,
    encounter_id: str,
    source: str,
    payload: dict[str, Any] | None = None,
    occurred_at: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_contract_identifiers(
        patient_id=patient_id,
        encounter_id=encounter_id,
        ctas_level="L3",
        zone="yellow",
    )
    if not event_type or not str(event_type).strip():
        raise ValueError("event_type is required")
    if not source or not str(source).strip():
        raise ValueError("source is required")
    envelope = {
        "event_id": event_id or f"evt-{uuid.uuid4().hex[:12]}",
        "event_type": str(event_type).strip(),
        "occurred_at": occurred_at or utc_now_iso(),
        "patient_id": normalized["patient_id"],
        "encounter_id": normalized["encounter_id"],
        "source": str(source).strip(),
        "payload": dict(payload or {}),
    }
    return envelope
