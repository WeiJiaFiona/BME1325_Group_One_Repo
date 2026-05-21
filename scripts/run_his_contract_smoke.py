from __future__ import annotations

import json

from app_core.his.adapters import (
    build_event_envelope,
    derive_zone_from_ctas,
    get_contract_field_mappings,
    get_contract_route_names,
    get_event_envelope_fields,
    normalize_contract_identifiers,
)


def build_contract_alignment_smoke_result() -> dict[str, object]:
    normalized = normalize_contract_identifiers(
        patient_id="P-1a2b3c4d",
        encounter_id="E-20260515153045-1a2b",
        ctas_level="L2",
        zone="orange",
    )
    envelope = build_event_envelope(
        event_type="handoff_requested",
        patient_id=normalized["patient_id"],
        encounter_id=normalized["encounter_id"],
        source="his_contract_smoke",
        payload={"target_system": "ICU"},
    )
    return {
        "name": "contract_alignment_checks",
        "status": "ok",
        "routes": list(get_contract_route_names()),
        "event_envelope_fields": list(get_event_envelope_fields()),
        "normalized": normalized,
        "derived_zone_l3": derive_zone_from_ctas("L3"),
        "envelope": envelope,
        "field_mappings": [
            {
                "source_field": item.source_field,
                "contract_field": item.contract_field,
                "notes": item.notes,
            }
            for item in get_contract_field_mappings()
        ],
    }


def main() -> None:
    print(json.dumps(build_contract_alignment_smoke_result(), indent=2))


if __name__ == "__main__":
    main()
