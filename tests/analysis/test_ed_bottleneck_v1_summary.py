from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (REPO_ROOT, REPO_ROOT / "scripts" / "cluster"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from build_ed_bottleneck_v1_summary import build_summary


def _scenario_payload(scenario_id: str = "scenario_a") -> dict:
    return {
        "scenario_id": scenario_id,
        "experiment_group": "nurse_capacity_sweep",
        "hospital_profile": "small_county_ed",
        "load_factor": 2.0,
        "run_steps": 1440,
        "seed": 42,
        "doctor_count": 2,
        "nurse_count_total": 7,
        "triage_nurse_count": 1,
        "bedside_nurse_count": 6,
        "bedside_nurse_service_time_multiplier": 1.0,
        "low_ctas_fast_track_enabled": False,
        "low_ctas_fast_track_fraction": 0.0,
    }


def _valid_report() -> dict:
    return {
        "total_arrived_patients": 28,
        "failure_rate": 0.4,
        "failure_based_success_rate": 0.6,
        "queue_success_rate": 0.5,
        "ctas_success_rate": 0.8,
        "throughput_success_rate": 0.7,
        "operational_success_rate": 0.5,
        "queue_exposed_patients": 14,
        "bedside_nurse_queue_exposed_patients": 13,
        "completed_care_count": 20,
        "still_in_ed_count": 8,
        "evidence_completeness": {"max_doctor_queue": 2},
    }


def test_summary_builder_generates_outputs_from_synthetic_status_and_report(tmp_path: Path):
    output_root = tmp_path / "cluster_outputs" / "ed_bottleneck_v1"
    scenario_dir = output_root / "nurse_capacity_sweep" / "scenario_a"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario_status.json").write_text(
        json.dumps({"status": "success", "scenario": _scenario_payload(), "result_row": {"failure_rate": None}}),
        encoding="utf-8",
    )
    (scenario_dir / "success_failure_report.json").write_text(json.dumps(_valid_report()), encoding="utf-8")

    analysis_dir = tmp_path / "analysis"
    summary = build_summary(output_root=output_root, analysis_dir=analysis_dir)

    assert summary["scenario_count"] == 1
    assert summary["valid_report_count"] == 1
    assert (analysis_dir / "ed_bottleneck_v1_summary.csv").exists()
    assert (analysis_dir / "ed_bottleneck_v1_summary.json").exists()
    assert (analysis_dir / "ed_bottleneck_v1_summary.md").exists()
    assert (analysis_dir / "ed_bottleneck_v1_plot_ready.csv").exists()

    with (analysis_dir / "ed_bottleneck_v1_summary.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["bedside_nurse_queue_exposed_patients"] == "13"
    assert rows[0]["report_valid"] == "True"


def test_summary_builder_marks_missing_report_invalid_without_crashing(tmp_path: Path):
    output_root = tmp_path / "cluster_outputs" / "ed_bottleneck_v1"
    scenario_dir = output_root / "time_window_check" / "scenario_missing_report"
    scenario_dir.mkdir(parents=True)
    scenario = _scenario_payload("scenario_missing_report")
    scenario["experiment_group"] = "time_window_check"
    (scenario_dir / "scenario_status.json").write_text(
        json.dumps({"status": "success", "scenario": scenario}),
        encoding="utf-8",
    )

    summary = build_summary(output_root=output_root, analysis_dir=tmp_path / "analysis")

    assert summary["scenario_count"] == 1
    assert summary["valid_report_count"] == 0
    assert summary["invalid_report_count"] == 1
    assert summary["rows"][0]["report_valid"] is False
    assert summary["rows"][0]["failure_rate"] is None
