import json
from pathlib import Path

from analysis.preload_sensitivity_report import dominant_failure_reason
from scripts.run_preload_sensitivity import (
    build_planned_runs,
    load_preload_matrix,
    run_preload_sensitivity,
)


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "configs" / "preload_sensitivity_matrix.csv"


def test_load_preload_matrix():
    rows = load_preload_matrix(MATRIX)
    assert rows
    assert "scenario_id" in rows[0]


def test_planned_runs_have_required_fields():
    planned = build_planned_runs(load_preload_matrix(MATRIX))
    row = planned[0]
    for key in (
        "scenario_id",
        "hospital_profile",
        "doctor_count",
        "nurse_count",
        "normal_patient_count",
        "load_factor",
        "preload_patient_count",
        "arrival_profile_mode",
        "background_arrival_enabled",
        "boarding_profile",
        "ctas_distribution",
        "seed",
        "run_steps",
    ):
        assert key in row


def test_preload_patient_count_formula():
    planned = build_planned_runs(load_preload_matrix(MATRIX))
    for row in planned:
        assert row["preload_patient_count"] == round(row["normal_patient_count"] * row["load_factor"])


def test_dry_run_generates_report(tmp_path: Path):
    output_path = tmp_path / "preload_sensitivity_report.json"
    report = run_preload_sensitivity(
        matrix=MATRIX,
        output=output_path,
        dry_run=True,
        run_real=False,
        max_scenarios=3,
    )
    assert output_path.exists()
    assert report["mode"] == "dry_run"
    assert report["scenario_count"] == 3
    assert report["results"][0]["run_status"] == "planned"


def test_dominant_failure_reason():
    assert dominant_failure_reason({"boarding_timeout": 2, "walkout_lwbs": 5}) == "walkout_lwbs"
    assert dominant_failure_reason({}) is None


def test_report_schema_stable(tmp_path: Path):
    output_path = tmp_path / "preload_sensitivity_report.json"
    report = run_preload_sensitivity(
        matrix=MATRIX,
        output=output_path,
        dry_run=True,
        run_real=False,
        max_scenarios=1,
    )
    for key in ("generated_at", "mode", "source_matrix", "scenario_count", "success_count", "results"):
        assert key in report


def test_blocked_if_preload_injection_missing(tmp_path: Path, monkeypatch):
    output_path = tmp_path / "preload_sensitivity_report.json"

    def fake_run_smoke(**kwargs):
        return {"status": "failed", "error": "preload injection path not available", "failure_stage": "save_settings"}

    monkeypatch.setattr("scripts.run_preload_sensitivity.run_smoke", fake_run_smoke)
    report = run_preload_sensitivity(
        matrix=MATRIX,
        output=output_path,
        dry_run=False,
        run_real=True,
        max_scenarios=1,
    )
    assert report["mode"] == "real_run"
    assert report["results"][0]["run_status"] == "failed"
    assert "preload injection" in report["results"][0]["notes"]


def test_known_movement_environment_mismatch_not_phase4_blocker(tmp_path: Path, monkeypatch):
    output_path = tmp_path / "preload_sensitivity_report.json"
    sim_dir = tmp_path / "sim"
    sim_dir.mkdir()
    sim_status_path = sim_dir / "sim_status.json"
    sim_status_path.write_text(
        json.dumps(
            {
                "queues": {"doctor_global": 3, "lab_waiting": 1, "imaging_waiting": 0},
                "doctors_total": 4,
            }
        ),
        encoding="utf-8",
    )

    def fake_run_smoke(**kwargs):
        return {
            "status": "success",
            "target": "fake_target",
            "sim_dir": str(sim_dir),
            "movement_files_count": 5,
            "strict_verify_passed": True,
            "resource_summary": {
                "total_arrived_patients": 10,
                "failure_rate": 0.2,
                "failed_patients_count": 2,
                "system_failed": True,
                "failure_reason_counts": {"boarding_timeout": 2},
            },
            "sim_status_path": str(sim_status_path),
            "failure_report_path": str(sim_dir / "analysis" / "failure_report.json"),
            "verify_normal": {"returncode": 1, "stdout": "target != environment/", "stderr": ""},
        }

    monkeypatch.setattr("scripts.run_preload_sensitivity.run_smoke", fake_run_smoke)
    report = run_preload_sensitivity(
        matrix=MATRIX,
        output=output_path,
        dry_run=False,
        run_real=True,
        max_scenarios=1,
    )
    result = report["results"][0]
    assert result["run_status"] == "success"
    assert result["week13_failure_metrics_verify"] == "passed"
    assert result["full_step_contract_status"] == "failed_known_movement_environment_mismatch"
