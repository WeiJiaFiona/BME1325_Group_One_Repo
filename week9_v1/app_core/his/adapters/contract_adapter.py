from __future__ import annotations

from dataclasses import dataclass

from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES

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


def normalize_contract_identifiers(*, patient_id: str, encounter_id: str, ctas_level: str, zone: str) -> dict[str, str]:
    # This placeholder intentionally preserves the frozen output keys without
    # performing full validation or derivation yet.
    return {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ctas_level": ctas_level,
        "zone": zone,
    }


def get_contract_route_names() -> tuple[str, ...]:
    return FROZEN_ROUTE_NAMES


def get_event_envelope_fields() -> tuple[str, ...]:
    return EVENT_ENVELOPE_FIELDS


def build_event_envelope_placeholder(*, event_type: str, patient_id: str, encounter_id: str, source: str) -> dict[str, str]:
    # The adapter owns the normalization surface, but the concrete payload
    # assembly should wait for the HIS write-path integration phase.
    raise NotImplementedError(
        "TODO: build the contract event envelope after the HIS write-path and route payloads are wired."
    )


def derive_zone_from_ctas(ctas_level: str) -> str:
    # Zone derivation rules should be finalized against the teacher contract and
    # user-flow checkpoints before this becomes executable logic.
    raise NotImplementedError(
        "TODO: derive contract-facing zone from CTAS once the triage normalization rules are frozen."
    )
