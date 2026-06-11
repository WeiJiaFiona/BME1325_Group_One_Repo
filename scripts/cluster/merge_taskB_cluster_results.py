#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (
    REPO_ROOT,
    REPO_ROOT / "analysis",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from analysis.small_county_staffing_sensitivity import build_small_county_staffing_sensitivity_report
from analysis.build_success_failure_report import validate_success_failure_report


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_cluster_statuses(input_root: str | Path) -> list[dict[str, Any]]:
    input_root = Path(input_root)
    results: list[dict[str, Any]] = []
    if not input_root.exists():
        return results
    for status_path in sorted(input_root.glob("*/scenario_status.json")):
        try:
            payload = load_json(status_path)
        except Exception:
            continue
        if isinstance(payload, dict):
            payload["_scenario_status_path"] = str(status_path)
            results.append(payload)
    return results


def missing_item_to_scenario_id(item: str) -> str:
    parts = {}
    for chunk in str(item).split("|"):
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            parts[key] = value
        else:
            parts["staffing_profile"] = chunk
    staffing_profile = parts["staffing_profile"]
    load_factor = parts["lf"].replace(".", "p")
    seed = parts["seed"]
    return f"{staffing_profile}_lf{load_factor}_seed{seed}"


def _load_success_failure_report_for_status(payload: dict[str, Any]) -> dict[str, Any]:
    status_path = payload.get("_scenario_status_path")
    if not status_path:
        output_dir = payload.get("output_dir")
        if output_dir:
            report_path = Path(str(output_dir)) / "success_failure_report.json"
        else:
            raise FileNotFoundError("cluster status missing _scenario_status_path/output_dir")
    else:
        report_path = Path(str(status_path)).parent / "success_failure_report.json"
    report = load_json(report_path)
    if not isinstance(report, dict):
        raise ValueError(f"invalid success_failure_report payload: {report_path}")
    validate_success_failure_report(report)
    return report


def _row_from_status_and_report(payload: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    scenario = payload.get("scenario", {}) if isinstance(payload.get("scenario"), dict) else {}
    evidence = report.get("evidence_completeness", {}) if isinstance(report.get("evidence_completeness"), dict) else {}
    return {
        "hospital_profile": scenario.get("hospital_profile") or report.get("hospital_profile"),
        "staffing_profile": scenario.get("staffing_profile"),
        "load_factor": float(scenario.get("load_factor")),
        "seed": int(scenario.get("seed")),
        "doctor_count": int(scenario.get("doctor_count")),
        "nurse_count": int(scenario.get("nurse_count")),
        "normal_patient_count": scenario.get("normal_patient_count"),
        "preload_patient_count": scenario.get("preload_patient_count") or report.get("preload_patient_count"),
        "total_arrived_patients": report.get("total_arrived_patients"),
        "failure_rate": report.get("failure_rate"),
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
        "sim_dir": payload.get("sim_dir") or payload.get("resolved_sim_dir"),
        "target_sim": payload.get("target_sim"),
        "artifact_status": payload.get("artifact_status") or "cluster_report",
    }


def merge_partial_with_cluster_results(partial_report: dict[str, Any], cluster_statuses: list[dict[str, Any]]) -> dict[str, Any]:
    combined_rows = list(partial_report.get("rows", []))
    existing_keys = {
        (
            str(row.get("staffing_profile")),
            float(row.get("load_factor")),
            int(row.get("seed")),
            int(row.get("doctor_count")),
            int(row.get("nurse_count")),
        )
        for row in combined_rows
        if row.get("load_factor") is not None and row.get("seed") is not None
    }
    completed_cluster_scenarios: list[str] = []
    failed_cluster_scenarios: list[str] = []

    for payload in cluster_statuses:
        status = str(payload.get("status"))
        scenario = payload.get("scenario", {}) or {}
        scenario_id = str(scenario.get("scenario_id") or "")
        if status == "success":
            try:
                report = _load_success_failure_report_for_status(payload)
                row = _row_from_status_and_report(payload, report)
                key = (
                    str(row.get("staffing_profile")),
                    float(row.get("load_factor")),
                    int(row.get("seed")),
                    int(row.get("doctor_count")),
                    int(row.get("nurse_count")),
                )
                completed_cluster_scenarios.append(scenario_id)
                if key not in existing_keys:
                    combined_rows.append(row)
                    existing_keys.add(key)
            except Exception:
                if scenario_id:
                    failed_cluster_scenarios.append(scenario_id)
        elif scenario_id:
            failed_cluster_scenarios.append(scenario_id)

    merged = build_small_county_staffing_sensitivity_report(combined_rows)
    previous_missing = list(partial_report.get("missing_scenarios", []))
    completed_set = set(completed_cluster_scenarios)
    still_missing = [item for item in previous_missing if missing_item_to_scenario_id(item) not in completed_set]

    merged["report_status"] = "completed" if not still_missing else "partial_completed"
    merged["completed_cluster_scenarios"] = completed_cluster_scenarios
    merged["failed_cluster_scenarios"] = failed_cluster_scenarios
    merged["remaining_missing_scenarios"] = still_missing
    return merged


def write_outputs(report: dict[str, Any], output_json: str | Path, output_md: str | Path, output_csv: str | Path) -> None:
    output_json = Path(output_json)
    output_md = Path(output_md)
    output_csv = Path(output_csv)
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    fieldnames = [
        "staffing_profile",
        "load_factor",
        "median_failure_rate",
        "fail_seed_count",
        "median_queue_success_rate",
        "median_ctas_success_rate",
        "median_operational_success_rate",
        "median_max_doctor_queue",
        "median_queue_exposed_patients",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report.get("aggregates", []):
            writer.writerow({key: row.get(key) for key in fieldnames})

    lines = [
        "# Small County Staffing Sensitivity Completed Report",
        "",
        f"- report_status: {report.get('report_status')}",
        f"- scenario_count: {report.get('scenario_count')}",
        "",
        "## Bottleneck Diagnosis",
        "",
        "```json",
        json.dumps(report.get("bottleneck_diagnosis", {}), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Remaining Missing Scenarios",
        "",
        "```json",
        json.dumps(report.get("remaining_missing_scenarios", []), indent=2, ensure_ascii=False),
        "```",
    ]
    output_md.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge cluster Task B outputs with the existing local partial report.")
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--existing-partial", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-csv", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    partial_report = load_json(args.existing_partial)
    cluster_statuses = load_cluster_statuses(args.input_root)
    report = merge_partial_with_cluster_results(partial_report, cluster_statuses)
    write_outputs(report, args.output_json, args.output_md, args.output_csv)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
