import csv
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"


def test_hospital_level_profiles_exist_and_match_formula():
    path = CONFIGS / "hospital_level_profiles.json"
    assert path.exists()

    with path.open("r", encoding="utf-8") as f:
        profiles = json.load(f)

    for name in ("large_tertiary_ed", "medium_city_ed", "small_county_ed"):
        assert name in profiles

    for profile_name, payload in profiles.items():
        for required_key in (
            "doctor_count",
            "nurse_count",
            "standard_patients_per_doctor",
            "standard_patients_per_nurse",
            "normal_patient_count",
            "load_factors",
            "evidence_note",
        ):
            assert required_key in payload, f"{profile_name} missing {required_key}"

        expected = min(
            payload["doctor_count"] * payload["standard_patients_per_doctor"],
            payload["nurse_count"] * payload["standard_patients_per_nurse"],
        )
        assert payload["normal_patient_count"] == expected
        assert str(payload["evidence_note"]).strip()


def test_preload_sensitivity_matrix_exists_and_uses_round_formula():
    profiles_path = CONFIGS / "hospital_level_profiles.json"
    matrix_path = CONFIGS / "preload_sensitivity_matrix.csv"
    assert matrix_path.exists()

    with profiles_path.open("r", encoding="utf-8") as f:
        profiles = json.load(f)

    with matrix_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert rows
    for row in rows:
        hospital_profile = row["hospital_profile"]
        assert hospital_profile in profiles
        normal_patient_count = int(row["normal_patient_count"])
        load_factor = float(row["load_factor"])
        preload_patient_count = int(row["preload_patient_count"])
        assert normal_patient_count == profiles[hospital_profile]["normal_patient_count"]
        assert preload_patient_count == round(normal_patient_count * load_factor)


def test_single_time_preload_shock_matrix_exists():
    path = CONFIGS / "single_time_preload_shock_matrix.csv"
    assert path.exists()


def test_failure_rate_threshold_search_yaml_exists():
    path = CONFIGS / "failure_rate_threshold_search.yaml"
    assert path.exists()
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    assert isinstance(payload, dict)
    assert payload.get("failure_threshold") == 0.1
    assert payload.get("system_failed_comparator") == "gt"
