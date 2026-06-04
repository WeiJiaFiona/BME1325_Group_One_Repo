import json
from pathlib import Path

from analysis.failure_report import write_failure_report


def test_failure_report_uses_sim_status_only_when_data_collection_missing(tmp_path: Path):
    sim_dir = tmp_path / "curr_sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "sim_status.json").write_text(
        json.dumps(
            {
                "step": 12,
                "resources": {
                    "total_arrived_patients": 10,
                    "failed_patients_count": 2,
                    "failure_rate": 0.2,
                    "system_failed": True,
                    "failure_threshold": 0.1,
                    "system_failed_comparator": "gt",
                    "failure_reason_counts": {"boarding_timeout": 2},
                }
            }
        ),
        encoding="utf-8",
    )

    report = write_failure_report(sim_dir)

    assert report["arrivals_total"] == 10
    assert report["failed_patients_count"] == 2
    assert report["failure_rate"] == 0.2
    assert report["patient_level_detail_available"] is False
    assert report["failed_patients"] == []


def test_failure_report_rebuilds_patient_level_detail_from_data_collection(tmp_path: Path):
    sim_dir = tmp_path / "curr_sim"
    reverie_dir = sim_dir / "reverie"
    reverie_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "sim_status.json").write_text(json.dumps({"step": 35}), encoding="utf-8")
    (reverie_dir / "data_collection.json").write_text(
        json.dumps(
            {
                "Patient": {
                    "patient_001": {"boarding_timeout_event": {"occurred": True}},
                    "patient_002": {"left_department_by_choice": {"occurred": True}},
                }
            }
        ),
        encoding="utf-8",
    )

    report = write_failure_report(sim_dir)

    assert report["patient_level_detail_available"] is True
    assert set(report["failed_patients"]) == {"patient_001", "patient_002"}
    assert report["failure_reasons_by_patient"]["patient_001"] == ["boarding_timeout"]
    assert report["failure_reasons_by_patient"]["patient_002"] == ["walkout_lwbs"]
    assert report["failed_at_step"]["patient_001"] == 35
