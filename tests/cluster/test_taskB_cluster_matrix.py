from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "scripts" / "cluster",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from merge_taskB_cluster_results import load_cluster_statuses, merge_partial_with_cluster_results
from run_one_taskB_scenario_headless import load_scenarios, read_scenario_row


def test_cluster_csv_has_10_rows_and_unique_ids():
    csv_path = REPO_ROOT / "configs" / "cluster" / "taskB_missing_scenarios.csv"
    rows = load_scenarios(csv_path)
    assert len(rows) == 10
    scenario_ids = [row["scenario_id"] for row in rows]
    assert len(scenario_ids) == len(set(scenario_ids))


def test_row_index_reads_correct_scenario():
    csv_path = REPO_ROOT / "configs" / "cluster" / "taskB_missing_scenarios.csv"
    first = read_scenario_row(csv_path, 1)
    last = read_scenario_row(csv_path, 10)
    assert first["scenario_id"] == "nurse_plus_lf1p0_seed44"
    assert last["scenario_id"] == "both_plus_lf2p0_seed44"


def test_slurm_array_range_is_1_to_10():
    slurm_path = REPO_ROOT / "scripts" / "cluster" / "submit_taskB_missing_cpu_array.slurm"
    text = slurm_path.read_text(encoding="utf-8")
    match = re.search(r"#SBATCH --array=1-10%(\d+)", text)
    assert match is not None
    assert int(match.group(1)) <= 6


def test_merge_handles_missing_scenarios(tmp_path: Path):
    scenario_dir = tmp_path / "both_plus_lf1p0_seed42"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "success_failure_report.json").write_text(
        json.dumps(
            {
                "total_arrived_patients": 10,
                "failure_rate": 0.1,
                "queue_success_rate": 1.0,
                "ctas_success_rate": 1.0,
                "throughput_success_rate": 0.9,
                "operational_success_rate": 0.9,
                "queue_exposed_patients": 0,
                "throughput_window_warning": False,
                "evidence_completeness": {"max_doctor_queue": 4},
            }
        ),
        encoding="utf-8",
    )
    partial = {
        "rows": [
            {
                "staffing_profile": "baseline",
                "load_factor": 1.0,
                "seed": 42,
                "doctor_count": 2,
                "nurse_count": 4,
                "failure_rate": 0.2,
            }
        ],
        "missing_scenarios": [
            "both_plus|lf=1.0|seed=42|dc=3|nc=6",
            "both_plus|lf=1.0|seed=43|dc=3|nc=6",
        ],
    }
    cluster_statuses = [
        {
            "status": "success",
            "_scenario_status_path": str(scenario_dir / "scenario_status.json"),
            "scenario": {
                "scenario_id": "both_plus_lf1p0_seed42",
                "hospital_profile": "small_county_ed",
                "staffing_profile": "both_plus",
                "load_factor": 1.0,
                "seed": 42,
                "doctor_count": 3,
                "nurse_count": 6,
            },
            "result_row": {
                "staffing_profile": "both_plus",
                "load_factor": 1.0,
                "seed": 42,
                "doctor_count": 3,
                "nurse_count": 6,
                "failure_rate": 0.1,
                "queue_success_rate": 1.0,
                "ctas_success_rate": 1.0,
                "operational_success_rate": 0.9,
                "max_doctor_queue": 4,
                "queue_exposed_patients": 0,
                "artifact_status": "newly_run",
            },
        }
    ]
    report = merge_partial_with_cluster_results(partial, cluster_statuses)
    assert report["report_status"] == "partial_completed"
    assert "both_plus|lf=1.0|seed=43|dc=3|nc=6" in report["remaining_missing_scenarios"]


def test_merge_reads_dummy_scenario_status_json(tmp_path: Path):
    scenario_dir = tmp_path / "row1"
    scenario_dir.mkdir(parents=True)
    payload = {
        "status": "success",
        "scenario": {"scenario_id": "dummy"},
        "result_row": {
            "staffing_profile": "nurse_plus",
            "load_factor": 2.0,
            "seed": 44,
            "doctor_count": 2,
            "nurse_count": 6,
            "failure_rate": 0.3,
            "queue_success_rate": 0.7,
            "ctas_success_rate": 0.8,
            "operational_success_rate": 0.6,
            "max_doctor_queue": 10,
            "queue_exposed_patients": 4,
            "artifact_status": "newly_run",
        },
    }
    (scenario_dir / "scenario_status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (scenario_dir / "success_failure_report.json").write_text(
        json.dumps(
            {
                "total_arrived_patients": 10,
                "failure_rate": 0.3,
                "queue_success_rate": 0.7,
                "ctas_success_rate": 0.8,
                "throughput_success_rate": 0.6,
                "operational_success_rate": 0.6,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_cluster_statuses(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["scenario"]["scenario_id"] == "dummy"
