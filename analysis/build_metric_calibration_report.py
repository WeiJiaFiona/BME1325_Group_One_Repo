from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "analysis",
    REPO_ROOT / "reverie" / "backend_server",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from build_success_failure_report import build_success_failure_report, validate_success_failure_report
from success_metrics import (
    build_failure_composition,
    compute_ctas_success_metrics,
    compute_operational_success_metrics,
    compute_queue_success_metrics_by_thresholds,
    extract_patient_records,
    failure_based_success_rate,
)


DEFAULT_PROBE_REPORT = REPO_ROOT / "analysis" / "runtime_evidence_probe_report.json"
DEFAULT_COMPOSITION_OUTPUT = REPO_ROOT / "analysis" / "failure_composition_report.json"
DEFAULT_SENSITIVITY_OUTPUT = REPO_ROOT / "analysis" / "metric_sensitivity_report.json"
DEFAULT_CALIBRATED_OUTPUT = REPO_ROOT / "analysis" / "success_failure_report_calibrated.json"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "analysis" / "metric_calibration_summary.md"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_minute_from_status(status_payload: dict[str, Any], minutes_per_step: int) -> int:
    return int(status_payload.get("step", 0) or 0) * int(minutes_per_step)


def _sensitivity_entry(
    *,
    patient_records: dict[str, dict[str, Any]],
    total_arrived_patients: int,
    queue_exposure_record_count: int,
    doctor_threshold: int,
    non_queue_failed_patients: set[str],
    failure_based_value: float | None,
    throughput_success_rate: float | None,
    revised_ctas_success_rate: float | None,
) -> dict[str, Any]:
    queue_metrics = compute_queue_success_metrics_by_thresholds(
        patient_records=patient_records,
        total_arrived_patients=total_arrived_patients,
        queue_exposure_record_count=queue_exposure_record_count,
        doctor_threshold=doctor_threshold,
        bedside_threshold=10**9,
        lab_threshold=10**9,
        imaging_threshold=10**9,
    )
    queue_failure_patients = set()
    for patient_id, record in patient_records.items():
        payload = record.get("queue_exposure", {}) or {}
        doctor_minutes = ((payload.get("doctor") or {}).get("exposure_minutes", 0)) if isinstance(payload, dict) else 0
        if doctor_minutes > doctor_threshold:
            queue_failure_patients.add(patient_id)
    combined_failed_patients = set(non_queue_failed_patients) | queue_failure_patients
    failure_rate = len(combined_failed_patients) / float(total_arrived_patients) if total_arrived_patients > 0 else None
    failure_based = failure_based_success_rate(failure_rate)
    operational_metrics = compute_operational_success_metrics(
        failure_based_success_rate_value=failure_based,
        queue_success_rate=queue_metrics["queue_success_rate"],
        ctas_success_rate=revised_ctas_success_rate,
        throughput_success_rate=throughput_success_rate,
    )
    return {
        "doctor_queue_exposure_threshold_minutes": doctor_threshold,
        "failure_rate": failure_rate,
        "queue_success_rate": queue_metrics["queue_success_rate"],
        "operational_success_rate": operational_metrics["operational_success_rate"],
        "operational_bottleneck_metric": operational_metrics["operational_bottleneck_metric"],
        "queue_exposed_patients": queue_metrics["queue_exposed_patients"],
    }


def build_metric_calibration_report(
    *,
    sim_dir: str | Path,
    probe_report_path: str | Path = DEFAULT_PROBE_REPORT,
    composition_output_path: str | Path = DEFAULT_COMPOSITION_OUTPUT,
    sensitivity_output_path: str | Path = DEFAULT_SENSITIVITY_OUTPUT,
    calibrated_output_path: str | Path = DEFAULT_CALIBRATED_OUTPUT,
    summary_output_path: str | Path = DEFAULT_SUMMARY_OUTPUT,
) -> dict[str, Any]:
    sim_dir = Path(sim_dir).resolve()
    probe_report = _load_json(Path(probe_report_path))
    status_payload = _load_json(sim_dir / "sim_status.json")
    meta_payload = _load_json(sim_dir / "reverie" / "meta.json")
    data_collection = _load_json(sim_dir / "reverie" / "data_collection.json")
    patient_records = extract_patient_records(data_collection)
    base_report = build_success_failure_report(
        sim_dir=sim_dir,
        output_path=REPO_ROOT / "analysis" / "_tmp_success_failure_report.json",
        probe_report_path=probe_report_path,
    )

    total_arrived_patients = int(base_report["total_arrived_patients"])
    minutes_per_step = int(base_report["time_scale_minutes_per_step"])
    current_minute = _current_minute_from_status(status_payload, minutes_per_step)
    queue_exposure_record_count = int(base_report["evidence_completeness"]["queue_exposure_record_count"])

    composition = build_failure_composition(
        patient_records=patient_records,
        total_arrived_patients=total_arrived_patients,
        current_minute=current_minute,
        ctas_targets=meta_payload.get("ctas_target_wait_minutes"),
        doctor_queue_threshold=30,
    )
    Path(composition_output_path).write_text(json.dumps(composition, indent=2, ensure_ascii=False), encoding="utf-8")

    non_queue_failed_patients = set(composition["failed_patients"]) - set(composition["failed_patients_by_reason"]["queue_overflow_exposure"])
    old_ctas = compute_ctas_success_metrics(
        patient_records=patient_records,
        ctas_targets=meta_payload.get("ctas_target_wait_minutes"),
        include_pending_violations=False,
        current_minute=current_minute,
    )
    revised_ctas = compute_ctas_success_metrics(
        patient_records=patient_records,
        ctas_targets=meta_payload.get("ctas_target_wait_minutes"),
        include_pending_violations=True,
        current_minute=current_minute,
    )

    throughput_success_rate = base_report["throughput_success_rate"]
    sensitivity = {
        "hospital_profile": base_report["hospital_profile"],
        "load_factor": base_report["load_factor"],
        "time_scale_minutes_per_step": base_report["time_scale_minutes_per_step"],
        "run_steps_completed": base_report["run_steps_completed"],
        "threshold_scenarios": [
            _sensitivity_entry(
                patient_records=patient_records,
                total_arrived_patients=total_arrived_patients,
                queue_exposure_record_count=queue_exposure_record_count,
                doctor_threshold=threshold,
                non_queue_failed_patients=non_queue_failed_patients,
                failure_based_value=base_report["failure_based_success_rate"],
                throughput_success_rate=throughput_success_rate,
                revised_ctas_success_rate=revised_ctas["ctas_success_rate"],
            )
            for threshold in (30, 60, 90)
        ],
    }
    Path(sensitivity_output_path).write_text(json.dumps(sensitivity, indent=2, ensure_ascii=False), encoding="utf-8")

    calibrated_failure_rate = (
        composition["failed_patients_count"] / float(total_arrived_patients)
        if total_arrived_patients > 0
        else None
    )
    calibrated_failure_based_success_rate = failure_based_success_rate(calibrated_failure_rate)
    calibrated_operational = compute_operational_success_metrics(
        failure_based_success_rate_value=calibrated_failure_based_success_rate,
        queue_success_rate=base_report["queue_success_rate"],
        ctas_success_rate=revised_ctas["ctas_success_rate"],
        throughput_success_rate=throughput_success_rate,
    )

    calibrated_report = {
        **base_report,
        "failure_rate": calibrated_failure_rate,
        "failure_based_success_rate": calibrated_failure_based_success_rate,
        "ctas_success_rate": revised_ctas["ctas_success_rate"],
        "ctas_eligible_count": revised_ctas["ctas_eligible_count"],
        "ctas_on_time_count": revised_ctas["ctas_on_time_count"],
        "ctas_violation_count": revised_ctas["ctas_violation_count"],
        "ctas_violations_by_level": revised_ctas["ctas_violations_by_level"],
        "operational_success_rate": calibrated_operational["operational_success_rate"],
        "operational_bottleneck_metric": calibrated_operational["operational_bottleneck_metric"],
        "operational_metric_components": calibrated_operational["operational_metric_components"],
        "old_ctas_success_rate": old_ctas["ctas_success_rate"],
        "revised_ctas_success_rate": revised_ctas["ctas_success_rate"],
        "old_ctas_eligible_count": old_ctas["ctas_eligible_count"],
        "revised_ctas_eligible_count": revised_ctas["ctas_eligible_count"],
        "revised_ctas_on_time_count": revised_ctas["ctas_on_time_count"],
        "revised_ctas_violation_count": revised_ctas["ctas_violation_count"],
        "revised_ctas_violations_by_level": revised_ctas["ctas_violations_by_level"],
        "revised_ctas_metric_status": revised_ctas["ctas_metric_status"],
        "ctas_pending_violation_enabled": True,
        "failure_composition_report_path": str(Path(composition_output_path)),
        "metric_sensitivity_report_path": str(Path(sensitivity_output_path)),
    }
    calibrated_report["metric_status"] = {
        **dict(base_report.get("metric_status", {})),
        "failure_based_success_rate": "ok" if calibrated_failure_based_success_rate is not None else "evidence_incomplete",
        "ctas_success_rate": revised_ctas["ctas_metric_status"],
        "operational_success_rate": calibrated_operational["operational_metric_status"],
    }
    validate_success_failure_report(calibrated_report, patient_record_count=len(patient_records))
    Path(calibrated_output_path).write_text(json.dumps(calibrated_report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_lines = [
        "# Metric Calibration Summary",
        "",
        f"- hospital_profile: {base_report['hospital_profile']}",
        f"- load_factor: {base_report['load_factor']}",
        f"- baseline failure_rate: {base_report['failure_rate']}",
        f"- baseline queue_success_rate: {base_report['queue_success_rate']}",
        f"- old_ctas_success_rate: {old_ctas['ctas_success_rate']}",
        f"- revised_ctas_success_rate: {revised_ctas['ctas_success_rate']}",
        f"- old_ctas_eligible_count: {old_ctas['ctas_eligible_count']}",
        f"- revised_ctas_eligible_count: {revised_ctas['ctas_eligible_count']}",
        "",
        "## Queue Sensitivity",
        "",
        "```json",
        json.dumps(sensitivity, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Failure Composition",
        "",
        "```json",
        json.dumps(
            {
                "failed_patients_count": composition["failed_patients_count"],
                "failure_reason_counts": composition["failure_reason_counts"],
                "queue_exposed_patients": composition["queue_exposed_patients"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        "```",
    ]
    Path(summary_output_path).write_text("\n".join(summary_lines), encoding="utf-8")

    return {
        "failure_composition_report": composition,
        "metric_sensitivity_report": sensitivity,
        "success_failure_report_calibrated": calibrated_report,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Week13 metric calibration reports from an existing probe artifact.")
    parser.add_argument("--sim-dir", required=True)
    parser.add_argument("--probe-report", default=str(DEFAULT_PROBE_REPORT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_metric_calibration_report(sim_dir=args.sim_dir, probe_report_path=args.probe_report)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
