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

from build_runtime_evidence_report import build_runtime_evidence_report
from failure_metrics import collect_failure_metrics
from success_metrics import compute_success_metrics, extract_patient_records


DEFAULT_OUTPUT = REPO_ROOT / "analysis" / "success_failure_report.json"
DEFAULT_MD_OUTPUT = REPO_ROOT / "analysis" / "success_failure_report.md"
DEFAULT_PROBE_REPORT = REPO_ROOT / "analysis" / "runtime_evidence_probe_report.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _data_collection_path(sim_dir: Path) -> Path:
    nested_path = sim_dir / "reverie" / "data_collection.json"
    if nested_path.exists():
        return nested_path
    return sim_dir / "data_collection.json"


CORE_RATE_FIELDS = (
    "failure_rate",
    "queue_success_rate",
    "ctas_success_rate",
    "throughput_success_rate",
    "operational_success_rate",
)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * float(percentile)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def build_bedside_nurse_queue_telemetry(patient_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    exposure_minutes: list[float] = []
    exposed_count = 0
    for record in patient_records.values():
        queue_exposure = record.get("queue_exposure")
        if not isinstance(queue_exposure, dict):
            continue
        bedside_payload = queue_exposure.get("bedside_nurse")
        if not isinstance(bedside_payload, dict):
            continue
        raw_minutes = bedside_payload.get("exposure_minutes")
        try:
            minutes = float(raw_minutes or 0)
        except (TypeError, ValueError):
            minutes = 0.0
        exposure_minutes.append(minutes)
        if minutes > 0:
            exposed_count += 1
    return {
        "bedside_nurse_queue_exposed_patients": exposed_count,
        "bedside_nurse_exposure_reason_count": exposed_count,
        "median_bedside_nurse_exposure_minutes": _percentile(exposure_minutes, 0.5),
        "p90_bedside_nurse_exposure_minutes": _percentile(exposure_minutes, 0.9),
        "max_bedside_nurse_exposure_minutes": max(exposure_minutes) if exposure_minutes else None,
        "active_bedside_nurse_count_by_step_summary": None,
        "idle_bedside_nurse_count_by_step_summary": None,
        "bedside_nurse_utilization_mean": None,
        "bedside_nurse_utilization_p90": None,
        "bedside_nurse_utilization_status": "not_available",
    }


def build_bedside_nurse_mechanism_telemetry(
    *,
    data_collection: Any,
    patient_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reinsert_counts = {
        patient_id: int(record.get("bedside_reinsert_count", 0) or 0)
        for patient_id, record in patient_records.items()
    }
    reinsert_positive = {patient_id: count for patient_id, count in reinsert_counts.items() if count > 0}
    top_reinsert = [
        {"patient_id": patient_id, "bedside_reinsert_count": count}
        for patient_id, count in sorted(reinsert_positive.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

    served_patients: list[str] = []
    if isinstance(data_collection, dict):
        for role_name, role_payload in data_collection.items():
            if "bedside" not in str(role_name).lower() or not isinstance(role_payload, dict):
                continue
            for nurse_payload in role_payload.values():
                if not isinstance(nurse_payload, dict):
                    continue
                for entry in nurse_payload.get("Patients_Attended", []) or []:
                    if isinstance(entry, (list, tuple)) and entry:
                        served_patients.append(str(entry[0]))
                    elif isinstance(entry, dict) and entry.get("patient"):
                        served_patients.append(str(entry["patient"]))
    served_set = set(served_patients)
    bedside_exposed = set()
    for patient_id, record in patient_records.items():
        exposure = record.get("queue_exposure")
        bedside_payload = exposure.get("bedside_nurse") if isinstance(exposure, dict) else None
        if isinstance(bedside_payload, dict):
            try:
                minutes = float(bedside_payload.get("exposure_minutes", 0) or 0)
            except (TypeError, ValueError):
                minutes = 0.0
            if minutes > 0:
                bedside_exposed.add(patient_id)

    total_assignments = len(served_patients)
    unique_assignments = len(served_set)
    repetition_ratio = None
    if total_assignments > 0:
        repetition_ratio = 1.0 - (unique_assignments / float(total_assignments))

    return {
        "reinsert_patient_count": len(reinsert_positive),
        "max_reinsert_count": max(reinsert_positive.values()) if reinsert_positive else 0,
        "top_reinsert_patients": top_reinsert,
        "nurse_assignment_repetition_ratio": repetition_ratio,
        "patients_never_served_but_exposed_count": len(bedside_exposed - served_set),
        "patients_never_served_but_exposed": sorted(bedside_exposed - served_set),
        "patients_served_but_still_exposed": sorted(bedside_exposed & served_set),
    }


def validate_success_failure_report(report: dict[str, Any], *, patient_record_count: int | None = None) -> None:
    """Fail closed so completed simulations cannot publish empty scorecards."""
    arrived = int(report.get("total_arrived_patients") or 0)
    if patient_record_count is not None and patient_record_count > 0 and arrived <= 0:
        raise ValueError(
            "invalid success_failure_report: Patient records exist "
            f"({patient_record_count}) but total_arrived_patients={arrived}"
        )
    if arrived <= 0:
        raise ValueError("invalid success_failure_report: total_arrived_patients must be > 0")
    missing_rates = [field for field in CORE_RATE_FIELDS if report.get(field) is None]
    if missing_rates:
        raise ValueError(
            "invalid success_failure_report: core rate fields are null: "
            + ", ".join(missing_rates)
        )


def _load_runtime_probe_report(path: Path = DEFAULT_PROBE_REPORT) -> dict[str, Any]:
    payload = _load_json(path)
    return payload if isinstance(payload, dict) else {}


def build_success_failure_report(
    *,
    sim_dir: str | Path,
    output_path: str | Path = DEFAULT_OUTPUT,
    probe_report_path: str | Path | None = DEFAULT_PROBE_REPORT,
) -> dict[str, Any]:
    sim_dir = Path(sim_dir).resolve()
    status_payload = _load_json(sim_dir / "sim_status.json")
    data_collection = _load_json(_data_collection_path(sim_dir))
    meta_payload = _load_json(sim_dir / "reverie" / "meta.json")
    patient_records = extract_patient_records(data_collection)

    probe_report = {}
    if probe_report_path is not None and Path(probe_report_path).exists():
        probe_report = _load_runtime_probe_report(Path(probe_report_path))
    probe_sim_dir = probe_report.get("sim_dir")
    probe_matches_sim_dir = False
    if probe_sim_dir:
        try:
            probe_matches_sim_dir = Path(str(probe_sim_dir)).resolve() == sim_dir
        except OSError:
            probe_matches_sim_dir = False
    evidence_candidate = probe_report.get("runtime_evidence_completeness", probe_report) if probe_report else {}
    probe_matches_records = int(evidence_candidate.get("total_arrived_patients", -1) or 0) == len(patient_records)
    if not probe_report or not probe_matches_sim_dir or not probe_matches_records:
        evidence_report = build_runtime_evidence_report(
            sim_dir=sim_dir,
            output_path=REPO_ROOT / "analysis" / "_tmp_runtime_evidence_report.json",
        )
        if probe_report and isinstance(probe_report, dict):
            probe_report = {
                **probe_report,
                "sim_dir": str(sim_dir),
                "runtime_evidence_completeness": evidence_report,
            }
        else:
            probe_report = evidence_report
    evidence = probe_report.get("runtime_evidence_completeness", probe_report)

    resources = status_payload.get("resources", {}) if isinstance(status_payload, dict) else {}
    failure_metrics = collect_failure_metrics(
        personas={},
        data_collection=data_collection,
        meta=meta_payload,
        curr_time=status_payload.get("sim_time"),
        curr_step=int(status_payload.get("step", 0) or 0),
    )
    failure_rate = resources.get("failure_rate", failure_metrics.get("failure_rate"))
    total_arrived_patients = len(patient_records)
    if total_arrived_patients <= 0:
        total_arrived_patients = int(evidence.get("total_arrived_patients", resources.get("total_arrived_patients", 0)) or 0)
    queue_exposure_record_count = int(evidence.get("queue_exposure_record_count", 0) or 0)
    physical_window_minutes = evidence.get("physical_window_minutes")

    success_metrics = compute_success_metrics(
        patient_records=patient_records,
        total_arrived_patients=total_arrived_patients,
        failure_rate=failure_rate,
        queue_exposure_record_count=queue_exposure_record_count,
        physical_window_minutes=physical_window_minutes,
        ctas_targets=meta_payload.get("ctas_target_wait_minutes"),
    )

    metric_status = {
        "failure_based_success_rate": "ok" if success_metrics["failure_based_success_rate"] is not None else "evidence_incomplete",
        "queue_success_rate": success_metrics["queue_metric_status"],
        "ctas_success_rate": success_metrics["ctas_metric_status"],
        "throughput_success_rate": success_metrics["throughput_metric_status"],
        "operational_success_rate": success_metrics["operational_metric_status"],
    }

    bedside_telemetry = {
        **build_bedside_nurse_queue_telemetry(patient_records),
        **build_bedside_nurse_mechanism_telemetry(data_collection=data_collection, patient_records=patient_records),
    }

    report = {
        "hospital_profile": probe_report.get("hospital_profile"),
        "load_factor": probe_report.get("load_factor"),
        "preload_patient_count": probe_report.get("preload_patient_count"),
        "run_steps_completed": evidence.get("run_steps_completed"),
        "time_scale_minutes_per_step": evidence.get("time_scale_minutes_per_step", meta_payload.get("time_scale_minutes_per_step", 1)),
        "physical_window_minutes": physical_window_minutes,
        "total_arrived_patients": total_arrived_patients,
        "failure_rate": failure_rate,
        "failure_based_success_rate": success_metrics["failure_based_success_rate"],
        "failure_based_success_metric_role": success_metrics["failure_based_success_metric_role"],
        "queue_success_rate": success_metrics["queue_success_rate"],
        "ctas_success_rate": success_metrics["ctas_success_rate"],
        "throughput_success_rate": success_metrics["throughput_success_rate"],
        "operational_success_rate": success_metrics["operational_success_rate"],
        "operational_bottleneck_metric": success_metrics["operational_bottleneck_metric"],
        "evidence_completeness": evidence,
        "metric_status": metric_status,
        "queue_exposed_patients": success_metrics["queue_exposed_patients"],
        "queue_exposure_reason_counts": success_metrics["queue_exposure_reason_counts"],
        "ctas_eligible_count": success_metrics["ctas_eligible_count"],
        "ctas_on_time_count": success_metrics["ctas_on_time_count"],
        "ctas_violation_count": success_metrics["ctas_violation_count"],
        "ctas_violations_by_level": success_metrics["ctas_violations_by_level"],
        "completed_care_count": success_metrics["completed_care_count"],
        "still_in_ed_count": success_metrics["still_in_ed_count"],
        "throughput_window_warning": success_metrics["throughput_window_warning"],
        "operational_metric_components": success_metrics["operational_metric_components"],
        **bedside_telemetry,
    }
    validate_success_failure_report(report, patient_record_count=len(patient_records))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown_report(report, output_path.with_suffix(".md"))
    return report


def _write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Success / Failure Report",
        "",
        f"- hospital_profile: {report.get('hospital_profile')}",
        f"- load_factor: {report.get('load_factor')}",
        f"- preload_patient_count: {report.get('preload_patient_count')}",
        f"- run_steps_completed: {report.get('run_steps_completed')}",
        f"- time_scale_minutes_per_step: {report.get('time_scale_minutes_per_step')}",
        f"- physical_window_minutes: {report.get('physical_window_minutes')}",
        "",
        "## Metrics",
        "",
        f"- failure_rate: {report.get('failure_rate')}",
        f"- failure_based_success_rate: {report.get('failure_based_success_rate')}",
        f"- queue_success_rate: {report.get('queue_success_rate')}",
        f"- ctas_success_rate: {report.get('ctas_success_rate')}",
        f"- throughput_success_rate: {report.get('throughput_success_rate')}",
        f"- operational_success_rate: {report.get('operational_success_rate')}",
        f"- operational_bottleneck_metric: {report.get('operational_bottleneck_metric')}",
        "",
        "## Metric Status",
        "",
        "```json",
        json.dumps(report.get("metric_status", {}), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Evidence Completeness",
        "",
        "```json",
        json.dumps(report.get("evidence_completeness", {}), indent=2, ensure_ascii=False),
        "```",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Week13 success/failure report from probe artifacts.")
    parser.add_argument("--sim-dir", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--probe-report", default=str(DEFAULT_PROBE_REPORT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_success_failure_report(
        sim_dir=args.sim_dir,
        output_path=args.output,
        probe_report_path=args.probe_report,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
