from __future__ import annotations


def normalize_contract_identifiers(*, patient_id: str, encounter_id: str, ctas_level: str, zone: str) -> dict[str, str]:
    return {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ctas_level": ctas_level,
        "zone": zone,
    }
