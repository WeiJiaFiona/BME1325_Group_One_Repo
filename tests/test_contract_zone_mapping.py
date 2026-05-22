from app_core.his.adapters.contract_adapter import (
    FROZEN_ZONE_VALUES,
    derive_zone_from_ctas,
    normalize_contract_identifiers,
)


def test_contract_zone_vocabulary_is_trimmed() -> None:
    assert FROZEN_ZONE_VALUES == ("red", "yellow", "green")


def test_derive_zone_from_ctas_matches_contract_v1() -> None:
    assert derive_zone_from_ctas("L1") == "red"
    assert derive_zone_from_ctas("L2") == "red"
    assert derive_zone_from_ctas("L3") == "yellow"
    assert derive_zone_from_ctas("L4") == "green"
    assert derive_zone_from_ctas("L5") == "green"


def test_normalize_contract_identifiers_rejects_non_contract_zone() -> None:
    try:
        normalize_contract_identifiers(
            patient_id="P-1a2b3c4d",
            encounter_id="E-20260515153045-1a2b",
            ctas_level="L2",
            zone="orange",
        )
    except ValueError as exc:
        assert "zone must be one of" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-contract zone value")

