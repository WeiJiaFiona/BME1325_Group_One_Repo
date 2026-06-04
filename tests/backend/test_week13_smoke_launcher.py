from __future__ import annotations

from pathlib import Path

from scripts.run_week13_smoke import (
    build_run_command_payload,
    build_smoke_summary,
    detect_target_mismatch,
    find_missing_failure_fields,
    required_failure_field_paths,
    resolve_target_sim_dir,
    validate_requested_target_artifacts,
)


def test_missing_failure_fields_detection():
    payload = {"resources": {}, "system_health": {}}
    missing = find_missing_failure_fields(payload)
    assert "resources.failure_rate" in missing
    assert "resources.failed_patients_count" in missing
    assert "system_health.failed" in missing


def test_complete_failure_fields_pass():
    payload = {
        "resources": {
            "total_arrived_patients": 0,
            "failed_patients_count": 0,
            "failure_rate": 0.0,
            "system_failed": False,
            "failure_threshold": 0.1,
            "system_failed_comparator": "gt",
            "failure_reason_counts": {},
            "lwbs_count": 0,
            "boarding_timeout_count": 0,
            "ctas_target_wait_violation_count": 0,
            "ed_los_over_threshold_count": 0,
            "queue_overflow_exposure_count": 0,
            "severe_trauma_time_to_surgery_violation_count": 0,
            "critical_outcome_event_count": 0,
        },
        "system_health": {
            "failed": False,
            "failed_reason": None,
            "failure_rate": 0.0,
            "failed_at_step": None,
        },
    }
    assert find_missing_failure_fields(payload) == []


def test_latest_sim_dir_not_old_curr_sim(tmp_path: Path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    (storage_root / "curr_sim").mkdir()
    new_target = storage_root / "week13_smoke_test_a1"
    new_target.mkdir()
    resolved = resolve_target_sim_dir(storage_root, "week13_smoke_test_a1")
    assert resolved == new_target


def test_smoke_summary_schema():
    summary = build_smoke_summary(
        attempt_id=1,
        status="failed",
        target="week13_smoke_test",
        commands=["python scripts/run_week13_smoke.py"],
        missing_fields=["resources.failure_rate"],
        error="missing fields",
        failure_stage="failure_metrics_schema",
    )
    assert summary["attempt_id"] == 1
    assert summary["status"] == "failed"
    assert summary["target"] == "week13_smoke_test"
    assert summary["missing_fields"] == ["resources.failure_rate"]
    assert summary["commands"] == ["python scripts/run_week13_smoke.py"]


def test_endpoint_payload_for_run_command():
    payload = build_run_command_payload(5)
    assert payload == {"command": "run 5"}
    assert "resources.failure_rate" in required_failure_field_paths()


def test_smoke_helper_detects_target_mismatch(tmp_path: Path):
    sim_dir = tmp_path / "storage" / "week13_smoke_fixed"
    sim_dir.mkdir(parents=True)
    assert detect_target_mismatch(
        requested_target="week13_smoke_fixed",
        current_target="curr_sim",
        sim_dir=sim_dir,
    ) is True


def test_smoke_helper_rejects_old_curr_sim_evidence(tmp_path: Path):
    sim_dir = tmp_path / "storage" / "curr_sim"
    sim_dir.mkdir(parents=True)
    ok, reason = validate_requested_target_artifacts(
        requested_target="week13_smoke_fixed",
        current_target="curr_sim",
        sim_dir=sim_dir,
    )
    assert ok is False
    assert reason == "target_mismatch"


def test_smoke_helper_requires_sim_status_under_requested_target(tmp_path: Path):
    sim_dir = tmp_path / "storage" / "week13_smoke_fixed"
    movement_dir = sim_dir / "movement"
    movement_dir.mkdir(parents=True)
    (movement_dir / "0.json").write_text("{}", encoding="utf-8")
    ok, reason = validate_requested_target_artifacts(
        requested_target="week13_smoke_fixed",
        current_target="week13_smoke_fixed",
        sim_dir=sim_dir,
    )
    assert ok is False
    assert reason == "sim_status_missing"
