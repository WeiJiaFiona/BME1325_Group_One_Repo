from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "scripts" / "cluster",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from merge_taskB_cluster_results import merge_partial_with_cluster_results
from rebuild_cluster_success_reports import rebuild_cluster


def _write_sim_artifact(tmp_path: Path) -> Path:
    sim_dir = tmp_path / "storage" / "cluster_taskB_both_plus_lf2p0_seed44"
    (sim_dir / "reverie").mkdir(parents=True)
    (sim_dir / "analysis").mkdir(parents=True)
    (sim_dir / "movement").mkdir(parents=True)
    (sim_dir / "sim_status.json").write_text(
        json.dumps({"step": 999, "resources": {"failure_rate": 0.25, "total_arrived_patients": 4}}),
        encoding="utf-8",
    )
    (sim_dir / "reverie" / "meta.json").write_text(
        json.dumps({"time_scale_minutes_per_step": 1, "ctas_target_wait_minutes": {"2": 10, "3": 30}}),
        encoding="utf-8",
    )
    (sim_dir / "reverie" / "data_collection.json").write_text(
        json.dumps(
            {
                "Patient": {
                    "Patient 1": {
                        "CTAS_score": 2,
                        "triage_completed_minute": 0,
                        "first_doctor_contact_minute": 5,
                        "ed_exit_minute": 20,
                        "queue_exposure": {"doctor": {"exposure_minutes": 0}},
                    },
                    "Patient 2": {
                        "CTAS_score": 2,
                        "triage_completed_minute": 0,
                        "first_doctor_contact_minute": 15,
                        "ed_exit_minute": 35,
                        "queue_exposure": {"doctor": {"exposure_minutes": 45}},
                    },
                    "Patient 3": {
                        "CTAS_score": 3,
                        "triage_completed_minute": 0,
                        "first_doctor_contact_minute": 20,
                        "ed_exit_minute": 45,
                        "queue_exposure": {"doctor": {"exposure_minutes": 0}},
                    },
                    "Patient 4": {
                        "CTAS_score": 3,
                        "triage_completed_minute": 0,
                        "first_doctor_contact_minute": 25,
                        "ed_exit_minute": 55,
                        "queue_exposure": {"doctor": {"exposure_minutes": 0}},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (sim_dir / "analysis" / "queue_trace_by_step.jsonl").write_text(
        json.dumps({"doctor_queue_len": 2}) + "\n",
        encoding="utf-8",
    )
    return sim_dir


def _write_status(output_root: Path, sim_dir: Path) -> Path:
    scenario_dir = output_root / "small_county_both_plus_lf2p0_seed44_steps1000"
    scenario_dir.mkdir(parents=True)
    status = {
        "scenario_id": "small_county_both_plus_lf2p0_seed44_steps1000",
        "status": "success",
        "run_steps": 1000,
        "step_completed": 999,
        "movement_count": 1000,
        "sim_dir": str(sim_dir),
        "resolved_sim_dir": str(sim_dir),
        "target_sim": "cluster_taskB_both_plus_lf2p0_seed44",
        "scenario": {
            "scenario_id": "small_county_both_plus_lf2p0_seed44_steps1000",
            "hospital_profile": "small_county_ed",
            "staffing_profile": "both_plus",
            "load_factor": 2.0,
            "seed": 44,
            "doctor_count": 3,
            "nurse_count": 6,
            "normal_patient_count": 12,
            "preload_patient_count": 24,
            "run_steps": 1000,
            "time_scale_minutes_per_step": 1,
        },
        "result_row": {
            "total_arrived_patients": 0,
            "failure_rate": None,
            "queue_success_rate": None,
            "ctas_success_rate": None,
            "throughput_success_rate": None,
            "operational_success_rate": None,
        },
    }
    (scenario_dir / "scenario_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return scenario_dir


def test_rebuild_cluster_success_reports_updates_status_result_row(tmp_path: Path):
    sim_dir = _write_sim_artifact(tmp_path)
    output_root = tmp_path / "cluster_outputs"
    scenario_dir = _write_status(output_root, sim_dir)

    results = rebuild_cluster(output_root, strict=True)

    assert results[0]["valid"] is True
    report = json.loads((scenario_dir / "success_failure_report.json").read_text(encoding="utf-8"))
    status = json.loads((scenario_dir / "scenario_status.json").read_text(encoding="utf-8"))
    assert report["total_arrived_patients"] == 4
    assert report["queue_success_rate"] is not None
    assert status["success_failure_report_valid"] is True
    assert status["report_generation_source"] == "post_backend_rebuild"
    assert status["result_row"]["total_arrived_patients"] == 4
    assert status["result_row"]["load_factor"] == 2.0


def test_merge_rejects_success_status_with_bad_report(tmp_path: Path):
    output_root = tmp_path / "cluster_outputs"
    scenario_dir = output_root / "bad_scenario"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario_status.json").write_text(
        json.dumps(
            {
                "status": "success",
                "scenario": {
                    "scenario_id": "both_plus_lf2p0_seed44",
                    "staffing_profile": "both_plus",
                    "load_factor": 2.0,
                    "seed": 44,
                    "doctor_count": 3,
                    "nurse_count": 6,
                },
                "result_row": {"failure_rate": 0.1},
            }
        ),
        encoding="utf-8",
    )
    (scenario_dir / "success_failure_report.json").write_text(
        json.dumps(
            {
                "total_arrived_patients": 0,
                "failure_rate": None,
                "queue_success_rate": None,
                "ctas_success_rate": None,
                "throughput_success_rate": None,
                "operational_success_rate": None,
            }
        ),
        encoding="utf-8",
    )
    partial = {
        "rows": [],
        "missing_scenarios": ["both_plus|lf=2.0|seed=44|dc=3|nc=6"],
    }

    from merge_taskB_cluster_results import load_cluster_statuses

    report = merge_partial_with_cluster_results(partial, load_cluster_statuses(output_root))
    assert "both_plus_lf2p0_seed44" in report["failed_cluster_scenarios"]
    assert report["scenario_count"] == 0
