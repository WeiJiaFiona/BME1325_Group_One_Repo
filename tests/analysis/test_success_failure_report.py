from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "analysis",
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from build_success_failure_report import build_success_failure_report


def _write_synthetic_artifact(tmp_path: Path) -> tuple[Path, Path]:
    sim_dir = tmp_path / "sim"
    (sim_dir / "reverie").mkdir(parents=True)
    (sim_dir / "analysis").mkdir(parents=True)
    (sim_dir / "sim_status.json").write_text(
        json.dumps(
            {
                "step": 199,
                "resources": {
                    "total_arrived_patients": 4,
                    "failure_rate": 0.25,
                }
            }
        ),
        encoding="utf-8",
    )
    (sim_dir / "reverie" / "meta.json").write_text(
        json.dumps(
            {
                "time_scale_minutes_per_step": 1,
                "ctas_target_wait_minutes": {"2": 10, "3": 30},
            }
        ),
        encoding="utf-8",
    )
    (sim_dir / "reverie" / "data_collection.json").write_text(
        json.dumps(
            {
                "Patient": {
                    "p1": {
                        "CTAS_score": 2,
                        "triage_completed_minute": 0,
                        "first_doctor_contact_minute": 5,
                        "ed_exit_minute": 20,
                        "queue_exposure": {"doctor": {"exposure_minutes": 0}},
                    },
                    "p2": {
                        "CTAS_score": 2,
                        "triage_completed_minute": 0,
                        "first_doctor_contact_minute": 15,
                        "queue_exposure": {"doctor": {"exposure_minutes": 45}},
                    },
                    "p3": {
                        "disposition_status": "discharged",
                        "queue_exposure": {"bedside_nurse": {"exposure_minutes": 0}},
                    },
                    "p4": {
                        "queue_exposure": {"lab": {"exposure_minutes": 31}},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (sim_dir / "analysis" / "queue_trace_by_step.jsonl").write_text(json.dumps({"doctor_queue_len": 5}) + "\n", encoding="utf-8")
    probe_report = tmp_path / "probe.json"
    probe_report.write_text(
        json.dumps(
            {
                "hospital_profile": "small_county_ed",
                "load_factor": 3.0,
                "preload_patient_count": 36,
                "sim_dir": str(sim_dir),
                "runtime_evidence_completeness": {
                    "run_steps_completed": 200,
                    "time_scale_minutes_per_step": 1,
                    "physical_window_minutes": 200,
                    "total_arrived_patients": 4,
                    "queue_exposure_record_count": 4,
                    "missing_evidence_fields": [],
                },
            }
        ),
        encoding="utf-8",
    )
    return sim_dir, probe_report


def test_report_schema_stable(tmp_path: Path):
    sim_dir, probe_report = _write_synthetic_artifact(tmp_path)
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=probe_report)
    required = {
        "failure_rate",
        "failure_based_success_rate",
        "queue_success_rate",
        "ctas_success_rate",
        "throughput_success_rate",
        "operational_success_rate",
        "metric_status",
        "evidence_completeness",
    }
    assert required.issubset(report.keys())


def test_short_window_sets_throughput_warning(tmp_path: Path):
    sim_dir, probe_report = _write_synthetic_artifact(tmp_path)
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=probe_report)
    assert report["throughput_window_warning"] is True
    assert report["metric_status"]["throughput_success_rate"] == "ok_with_short_window_warning"


def test_evidence_incomplete_does_not_default_success_to_one(tmp_path: Path):
    sim_dir, probe_report = _write_synthetic_artifact(tmp_path)
    data_collection_path = sim_dir / "reverie" / "data_collection.json"
    payload = json.loads(data_collection_path.read_text(encoding="utf-8"))
    for row in payload["Patient"].values():
        row.pop("queue_exposure", None)
        row.pop("ed_exit_minute", None)
        row.pop("disposition_status", None)
    data_collection_path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=None)
    except ValueError as exc:
        assert "core rate fields are null" in str(exc)
    else:
        raise AssertionError("invalid report with null core rates should fail closed")


def test_report_builds_from_synthetic_or_real_artifact(tmp_path: Path):
    sim_dir, probe_report = _write_synthetic_artifact(tmp_path)
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=probe_report)
    assert report["hospital_profile"] == "small_county_ed"
    assert (tmp_path / "out.md").exists()


def test_stale_probe_evidence_rebuilds_from_patient_records(tmp_path: Path):
    sim_dir, probe_report = _write_synthetic_artifact(tmp_path)
    probe_payload = json.loads(probe_report.read_text(encoding="utf-8"))
    probe_payload["runtime_evidence_completeness"]["total_arrived_patients"] = 0
    probe_payload["runtime_evidence_completeness"]["queue_exposure_record_count"] = 0
    probe_report.write_text(json.dumps(probe_payload), encoding="utf-8")
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=probe_report)
    assert report["total_arrived_patients"] == 4
    assert report["evidence_completeness"]["total_arrived_patients"] == 4
    assert report["evidence_completeness"]["queue_exposure_record_count"] == 4


def test_direct_data_collection_path_supported(tmp_path: Path):
    sim_dir, probe_report = _write_synthetic_artifact(tmp_path)
    direct_path = sim_dir / "data_collection.json"
    nested_path = sim_dir / "reverie" / "data_collection.json"
    direct_path.write_text(nested_path.read_text(encoding="utf-8"), encoding="utf-8")
    nested_path.unlink()
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=None)
    assert report["total_arrived_patients"] == 4


def test_reverie_data_collection_preferred_over_stale_direct_path(tmp_path: Path):
    sim_dir, _probe_report = _write_synthetic_artifact(tmp_path)
    (sim_dir / "data_collection.json").write_text(json.dumps({"Patient": {}}), encoding="utf-8")
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=None)
    assert report["total_arrived_patients"] == 4


def test_patient_list_shape_counts_records(tmp_path: Path):
    sim_dir, _probe_report = _write_synthetic_artifact(tmp_path)
    payload = json.loads((sim_dir / "reverie" / "data_collection.json").read_text(encoding="utf-8"))
    (sim_dir / "reverie" / "data_collection.json").write_text(
        json.dumps({"Patient": list(payload["Patient"].values())}),
        encoding="utf-8",
    )
    report = build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=None)
    assert report["total_arrived_patients"] == 4


def test_patient_records_with_null_rates_raise(tmp_path: Path):
    sim_dir, _probe_report = _write_synthetic_artifact(tmp_path)
    payload = json.loads((sim_dir / "reverie" / "data_collection.json").read_text(encoding="utf-8"))
    for row in payload["Patient"].values():
        row.pop("queue_exposure", None)
        row.pop("ed_exit_minute", None)
        row.pop("disposition_status", None)
    (sim_dir / "reverie" / "data_collection.json").write_text(json.dumps(payload), encoding="utf-8")
    try:
        build_success_failure_report(sim_dir=sim_dir, output_path=tmp_path / "out.json", probe_report_path=None)
    except ValueError as exc:
        assert "core rate fields are null" in str(exc)
    else:
        raise AssertionError("builder should reject reports with Patient records but null core rates")
