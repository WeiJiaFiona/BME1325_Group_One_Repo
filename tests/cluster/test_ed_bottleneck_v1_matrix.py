from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (REPO_ROOT, REPO_ROOT / "scripts" / "cluster"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from run_one_ed_bottleneck_v1_scenario import read_scenario_row, scenario_output_dir


CSV_PATH = REPO_ROOT / "configs" / "cluster" / "ed_bottleneck_v1_scenarios.csv"
REQUIRED_FIELDS = {
    "scenario_id",
    "hospital_profile",
    "load_factor",
    "run_steps",
    "seed",
    "doctor_count",
    "nurse_count_total",
    "triage_nurse_count",
    "bedside_nurse_count",
    "bedside_nurse_service_time_multiplier",
    "low_ctas_fast_track_enabled",
    "low_ctas_fast_track_fraction",
    "experiment_group",
    "output_root",
}


def _rows() -> list[dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_ed_bottleneck_v1_csv_schema_and_unique_ids():
    rows = _rows()
    assert rows
    assert REQUIRED_FIELDS.issubset(rows[0].keys())
    scenario_ids = [row["scenario_id"] for row in rows]
    assert len(scenario_ids) == len(set(scenario_ids))


def test_each_scenario_has_experiment_group_and_allowed_steps():
    for row in _rows():
        assert row["experiment_group"]
        assert int(row["run_steps"]) in {1000, 1440, 2880}


def test_bedside_nurse_count_positive_and_multiplier_range():
    for row in _rows():
        assert int(row["bedside_nurse_count"]) > 0
        multiplier = float(row["bedside_nurse_service_time_multiplier"])
        assert 0 < multiplier <= 1.0


def test_expected_experiment_groups_present():
    groups = {row["experiment_group"] for row in _rows()}
    assert {
        "time_window_check",
        "nurse_capacity_sweep",
        "bedside_service_time_sweep",
        "large_tertiary_smoke",
    }.issubset(groups)


def test_runner_reads_row_and_uses_grouped_output_layout(tmp_path: Path):
    row = read_scenario_row(CSV_PATH, 1)
    output_dir = scenario_output_dir(tmp_path, row)
    assert output_dir == tmp_path / row["experiment_group"] / row["scenario_id"]
    assert isinstance(row["low_ctas_fast_track_enabled"], bool)
