from __future__ import annotations

import re

from app_core.his.adapters.contract_adapter import (
    ENCOUNTER_ID_PATTERN,
    FROZEN_CTAS_LEVELS,
    FROZEN_ZONE_VALUES,
    PATIENT_ID_PATTERN,
    build_event_envelope_placeholder,
    derive_zone_from_ctas,
    normalize_contract_identifiers,
    normalize_ctas_level,
)
from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES
from scripts.run_his_contract_smoke import build_contract_alignment_smoke_plan


def test_contract_id_patterns_match_freeze() -> None:
    assert re.fullmatch(PATIENT_ID_PATTERN, "P-1a2b3c4d")
    assert re.fullmatch(ENCOUNTER_ID_PATTERN, "E-20260508153045-1a2b")


def test_contract_routes_and_envelope_match_freeze() -> None:
    assert FROZEN_ROUTE_NAMES == ("transfer", "admissions", "summary", "timeline")
    assert EVENT_ENVELOPE_FIELDS == (
        "event_id",
        "event_type",
        "occurred_at",
        "patient_id",
        "encounter_id",
        "source",
        "payload",
    )
    assert FROZEN_CTAS_LEVELS == ("L1", "L2", "L3", "L4", "L5")
    assert FROZEN_ZONE_VALUES == ("red", "orange", "yellow", "green", "blue")


def test_contract_normalization_helpers_are_executable() -> None:
    normalized = normalize_contract_identifiers(
        patient_id="P-1a2b3c4d",
        encounter_id="E-20260508153045-1a2b",
        ctas_level=normalize_ctas_level("B"),
        zone="",
    )
    envelope = build_event_envelope_placeholder(
        event_type="triage_completed",
        patient_id=normalized["patient_id"],
        encounter_id=normalized["encounter_id"],
        source="tests_his",
        payload={"zone": derive_zone_from_ctas("L2")},
    )
    assert normalized["ctas_level"] == "L2"
    assert normalized["zone"] == "orange"
    assert tuple(envelope.keys()) == EVENT_ENVELOPE_FIELDS


def test_contract_smoke_script_passes() -> None:
    plan = build_contract_alignment_smoke_plan()
    assert plan["status"] == "passed"
    assert plan["field_checks"]["patient_id_matches"] is True
    assert plan["field_checks"]["encounter_id_matches"] is True
