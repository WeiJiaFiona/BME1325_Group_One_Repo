from __future__ import annotations

import re

from app_core.his.adapters.contract_adapter import (
    ENCOUNTER_ID_PATTERN,
    FROZEN_CTAS_LEVELS,
    FROZEN_ZONE_VALUES,
    PATIENT_ID_PATTERN,
)
from app_core.his.config import EVENT_ENVELOPE_FIELDS, FROZEN_ROUTE_NAMES


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
