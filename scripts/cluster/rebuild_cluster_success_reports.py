#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "analysis",
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from analysis.build_metric_calibration_report import build_metric_calibration_report
from analysis.build_runtime_evidence_report import build_runtime_evidence_report
from analysis.build_success_failure_report import validate_success_failure_report


CORE_METRIC_FIELDS = (
    "failure_rate",
    "queue_success_rate",
    "ctas_success_rate",
    "throughput_success_rate",
    "operational_success_rate",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _data_collection_path(sim_dir: Path) -> Path:
    nested_path = sim_dir / "reverie" / "data_collection.json"
    if nested_path.exists():
        return nested_path
    return sim_dir / "data_collection.json"


def _resolve_sim_dir(status: dict[str, Any]) -> Path:
    raw = status.get("sim_dir") or status.get("resolved_sim_dir")
    if not raw:
        raise ValueError("scenario_status missing sim_dir/resolved_sim_dir")
    return Path(str(raw)).resolve()


def _scenario_metadata(status: dict[str, Any], report: dict[str, Any] | None = None) -> dict[str, Any]:
    scenario = status.get("scenario") if isinstance(status.get("scenario"), dict) else {}
    report = report or {}
    return {
        "scenario_id": status.get("scenario_id") or scenario.get("scenario_id"),
        "hospital_profile": scenario.get("hospital_profile") or report.get("hospital_profile"),
        "staffing_profile": scenario.get("staffing_profile"),
        "load_factor": scenario.get("load_factor"),
        "seed": scenario.get("seed"),
        "doctor_count": scenario.get("doctor_count"),
        "nurse_count": scenario.get("nurse_count"),
        "run_steps": scenario.get("run_steps") or status.get("run_steps"),
        "time_scale_minutes_per_step": scenario.get("time_scale_minutes_per_step") or report.get("time_scale_minutes_per_step"),
    }


def _build_probe_envelope(
    *,
    status: dict[str, Any],
    sim_dir: Path,
    output_dir: Path,
) -> Path:
    scenario = status.get("scenario") if isinstance(status.get("scenario"), dict) else {}
    load_factor = scenario.get("load_factor")
    preload_patient_count = scenario.get("preload_patient_count")
    if preload_patient_count is None:
        normal_patient_count = scenario.get("normal_patient_count")
        if normal_patient_count is not None and load_factor is not None:
            preload_patient_count = round(int(normal_patient_count) * float(load_factor))

    probe_report = build_runtime_evidence_report(
        sim_dir=sim_dir,
        output_path=output_dir / "runtime_evidence_probe_report.json",
        hospital_profile=scenario.get("hospital_profile"),
        load_factor=float(load_factor) if load_factor is not None else None,
        preload_patient_count=preload_patient_count,
        run_steps_requested=int(scenario.get("run_steps") or status.get("run_steps") or 0) or None,
    )
    probe_envelope = {
        "hospital_profile": scenario.get("hospital_profile"),
        "load_factor": float(load_factor) if load_factor is not None else None,
        "preload_patient_count": preload_patient_count,
        "run_steps_requested": int(scenario.get("run_steps") or status.get("run_steps") or 0) or None,
        "run_steps_completed": probe_report["run_steps_completed"],
        "time_scale_minutes_per_step": probe_report["time_scale_minutes_per_step"],
        "physical_window_minutes": probe_report["physical_window_minutes"],
        "target_sim": status.get("target_sim") or scenario.get("target_sim"),
        "sim_dir": str(sim_dir),
        "runtime_evidence_completeness": probe_report,
    }
    probe_path = output_dir / "probe_envelope.json"
    _write_json(probe_path, probe_envelope)
    return probe_path


def _result_row_from_report(
    *,
    status: dict[str, Any],
    report: dict[str, Any],
    composition: dict[str, Any],
    sim_dir: Path,
) -> dict[str, Any]:
    meta = _scenario_metadata(status, report)
    evidence = report.get("evidence_completeness", {}) if isinstance(report.get("evidence_completeness"), dict) else {}
    return {
        **meta,
        "preload_patient_count": report.get("preload_patient_count"),
        "total_arrived_patients": report.get("total_arrived_patients"),
        "failure_rate": report.get("failure_rate"),
        "failure_reason_counts": composition.get("failure_reason_counts", {}),
        "queue_success_rate": report.get("queue_success_rate"),
        "ctas_success_rate": report.get("ctas_success_rate"),
        "throughput_success_rate": report.get("throughput_success_rate"),
        "operational_success_rate": report.get("operational_success_rate"),
        "max_doctor_queue": evidence.get("max_doctor_queue"),
        "queue_exposed_patients": report.get("queue_exposed_patients"),
        "first_doctor_contact_at_count": evidence.get("first_doctor_contact_at_count"),
        "ed_exit_at_count": evidence.get("ed_exit_at_count"),
        "runtime_evidence_completeness": evidence,
        "throughput_window_warning": report.get("throughput_window_warning"),
        "sim_dir": str(sim_dir),
        "target_sim": status.get("target_sim") or meta.get("scenario_id"),
        "artifact_status": status.get("artifact_status") or "rebuilt_from_cluster_artifacts",
    }


def rebuild_one(status_path: Path) -> dict[str, Any]:
    output_dir = status_path.parent
    status = _load_json(status_path)
    scenario_id = str(status.get("scenario_id") or output_dir.name)
    sim_dir = _resolve_sim_dir(status)
    data_collection_path = _data_collection_path(sim_dir)
    if not data_collection_path.exists():
        raise FileNotFoundError(f"missing data_collection: {data_collection_path}")

    probe_path = _build_probe_envelope(status=status, sim_dir=sim_dir, output_dir=output_dir)
    calibration = build_metric_calibration_report(
        sim_dir=sim_dir,
        probe_report_path=probe_path,
        composition_output_path=output_dir / "failure_composition_report.json",
        sensitivity_output_path=output_dir / "metric_sensitivity_report.json",
        calibrated_output_path=output_dir / "success_failure_report.json",
        summary_output_path=output_dir / "metric_calibration_summary.md",
    )
    report = calibration["success_failure_report_calibrated"]
    validate_success_failure_report(report)

    status["result_row"] = _result_row_from_report(
        status=status,
        report=report,
        composition=calibration["failure_composition_report"],
        sim_dir=sim_dir,
    )
    status["success_failure_report_exists"] = True
    status["success_failure_report_valid"] = True
    status["success_failure_report_rebuilt_from"] = str(data_collection_path)
    status["report_generation_source"] = "post_backend_rebuild"
    status["stage"] = "backend_only_completed" if status.get("status") == "success" else status.get("stage")
    status["error"] = None if status.get("status") == "success" else status.get("error")
    _write_json(status_path, status)

    return {
        "scenario_id": scenario_id,
        "total_arrived_patients": report.get("total_arrived_patients"),
        "failure_rate": report.get("failure_rate"),
        "queue_success_rate": report.get("queue_success_rate"),
        "ctas_success_rate": report.get("ctas_success_rate"),
        "throughput_success_rate": report.get("throughput_success_rate"),
        "operational_success_rate": report.get("operational_success_rate"),
        "valid": True,
    }


def rebuild_cluster(output_root: str | Path, *, strict: bool = False) -> list[dict[str, Any]]:
    output_root = Path(output_root)
    results: list[dict[str, Any]] = []
    bad_count = 0
    for status_path in sorted(output_root.glob("*/scenario_status.json")):
        try:
            result = rebuild_one(status_path)
        except Exception as exc:
            bad_count += 1
            result = {
                "scenario_id": status_path.parent.name,
                "total_arrived_patients": None,
                "failure_rate": None,
                "queue_success_rate": None,
                "ctas_success_rate": None,
                "throughput_success_rate": None,
                "operational_success_rate": None,
                "valid": False,
                "error": str(exc),
            }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))
    if strict and bad_count:
        raise SystemExit(1)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild cluster success/failure reports from existing artifacts.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rebuild_cluster(args.output_root, strict=bool(args.strict))


if __name__ == "__main__":
    main()
