from __future__ import annotations

import json

from app_core.his.adapters import get_contract_field_mappings, get_contract_route_names, get_event_envelope_fields


def build_contract_alignment_smoke_plan() -> dict[str, object]:
    return {
        "name": "contract_alignment_checks",
        "status": "placeholder",
        "blocked_by": ["Finalize teacher contract cross-check and HIS write-path integration."],
        "routes": list(get_contract_route_names()),
        "event_envelope_fields": list(get_event_envelope_fields()),
        "field_mappings": [
            {
                "source_field": item.source_field,
                "contract_field": item.contract_field,
                "notes": item.notes,
            }
            for item in get_contract_field_mappings()
        ],
        "checks": [
            "Verify patient_id and encounter_id frozen formats.",
            "Verify CTAS and zone normalization before outgoing HIS payloads.",
            "Verify event envelope keys match the frozen contract.",
            "Verify transfer/admissions/summary/timeline route names remain unchanged.",
        ],
    }


def main() -> None:
    print(json.dumps(build_contract_alignment_smoke_plan(), indent=2))


if __name__ == "__main__":
    main()
