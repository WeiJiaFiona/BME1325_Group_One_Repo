#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (REPO_ROOT, REPO_ROOT / "analysis"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from analysis.build_success_failure_report import validate_success_failure_report


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "ed_bottleneck_v1"
DEFAULT_ANALYSIS_DIR = REPO_ROOT / "analysis"

SUMMARY_FIELDS = [
    "experiment_group",
    "scenario_id",
    "hospital_profile",
    "load_factor",
    "run_steps",
    "seed",
    "doctor_count",
    "nurse_count_total",
    "triage_nurse_count",
    "bedside_nurse_count",
    "bedside_nurse_service_time_multiplier",
    "low_ctas_fast_track_enabled",
    "low_ctas_fast_track_fraction",
    "total_arrived_patients",
    "failure_rate",
    "queue_success_rate",
    "ctas_success_rate",
    "throughput_success_rate",
    "operational_success_rate",
    "queue_exposed_patients",
    "bedside_nurse_queue_exposed_patients",
    "completed_care_count",
    "still_in_ed_count",
    "report_valid",
]

PLOT_METRICS = [
    "failure_rate",
    "queue_success_rate",
    "ctas_success_rate",
    "throughput_success_rate",
    "operational_success_rate",
    "queue_exposed_patients",
    "bedside_nurse_queue_exposed_patients",
    "completed_care_count",
    "still_in_ed_count",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce(value: Any) -> Any:
    if value in ("", "none", "None"):
        return None
    return value


def _scenario_value(scenario: dict[str, Any], key: str) -> Any:
    return _coerce(scenario.get(key))


def _report_row(status_path: Path) -> dict[str, Any]:
    status = _load_json(status_path)
    scenario = status.get("scenario") if isinstance(status.get("scenario"), dict) else {}
    report_path = status_path.parent / "success_failure_report.json"
    report: dict[str, Any] = {}
    report_valid = False
    if report_path.exists():
        try:
            loaded = _load_json(report_path)
            if isinstance(loaded, dict):
                validate_success_failure_report(loaded)
                report = loaded
                report_valid = True
        except Exception:
            report = {}
            report_valid = False

    row = {
        "experiment_group": _scenario_value(scenario, "experiment_group") or status_path.parent.parent.name,
        "scenario_id": _scenario_value(scenario, "scenario_id") or status.get("scenario_id") or status_path.parent.name,
        "hospital_profile": _scenario_value(scenario, "hospital_profile"),
        "load_factor": _scenario_value(scenario, "load_factor"),
        "run_steps": _scenario_value(scenario, "run_steps") or status.get("run_steps"),
        "seed": _scenario_value(scenario, "seed"),
        "doctor_count": _scenario_value(scenario, "doctor_count"),
        "nurse_count_total": _scenario_value(scenario, "nurse_count_total"),
        "triage_nurse_count": _scenario_value(scenario, "triage_nurse_count"),
        "bedside_nurse_count": _scenario_value(scenario, "bedside_nurse_count"),
        "bedside_nurse_service_time_multiplier": _scenario_value(scenario, "bedside_nurse_service_time_multiplier"),
        "low_ctas_fast_track_enabled": _scenario_value(scenario, "low_ctas_fast_track_enabled"),
        "low_ctas_fast_track_fraction": _scenario_value(scenario, "low_ctas_fast_track_fraction"),
        "total_arrived_patients": report.get("total_arrived_patients") if report_valid else None,
        "failure_rate": report.get("failure_rate") if report_valid else None,
        "queue_success_rate": report.get("queue_success_rate") if report_valid else None,
        "ctas_success_rate": report.get("ctas_success_rate") if report_valid else None,
        "throughput_success_rate": report.get("throughput_success_rate") if report_valid else None,
        "operational_success_rate": report.get("operational_success_rate") if report_valid else None,
        "queue_exposed_patients": report.get("queue_exposed_patients") if report_valid else None,
        "bedside_nurse_queue_exposed_patients": report.get("bedside_nurse_queue_exposed_patients") if report_valid else None,
        "completed_care_count": report.get("completed_care_count") if report_valid else None,
        "still_in_ed_count": report.get("still_in_ed_count") if report_valid else None,
        "report_valid": report_valid,
    }
    return row


def build_summary(output_root: str | Path = DEFAULT_OUTPUT_ROOT, analysis_dir: str | Path = DEFAULT_ANALYSIS_DIR) -> dict[str, Any]:
    output_root = Path(output_root)
    analysis_dir = Path(analysis_dir)
    rows = [_report_row(path) for path in sorted(output_root.glob("*/*/scenario_status.json"))]
    analysis_dir.mkdir(parents=True, exist_ok=True)

    csv_path = analysis_dir / "ed_bottleneck_v1_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in SUMMARY_FIELDS})

    plot_rows: list[dict[str, Any]] = []
    for row in rows:
        group = str(row.get("experiment_group"))
        if group == "time_window_check":
            x_axis = "run_steps"
            x_value = row.get("run_steps")
        elif group == "nurse_capacity_sweep":
            x_axis = "bedside_nurse_count"
            x_value = row.get("bedside_nurse_count")
        elif group == "bedside_service_time_sweep":
            x_axis = "bedside_nurse_service_time_multiplier"
            x_value = row.get("bedside_nurse_service_time_multiplier")
        else:
            x_axis = "load_factor"
            x_value = row.get("load_factor")
        for metric in PLOT_METRICS:
            value = row.get(metric)
            if value is None:
                continue
            plot_rows.append(
                {
                    "x_axis": x_axis,
                    "x_value": x_value,
                    "group": group,
                    "metric_name": metric,
                    "metric_value": value,
                    "seed": row.get("seed"),
                    "scenario_id": row.get("scenario_id"),
                }
            )

    plot_path = analysis_dir / "ed_bottleneck_v1_plot_ready.csv"
    with plot_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["x_axis", "x_value", "group", "metric_name", "metric_value", "seed", "scenario_id"])
        writer.writeheader()
        writer.writerows(plot_rows)

    summary = {
        "scenario_count": len(rows),
        "valid_report_count": sum(1 for row in rows if row.get("report_valid") is True),
        "invalid_report_count": sum(1 for row in rows if row.get("report_valid") is not True),
        "rows": rows,
        "outputs": {
            "summary_csv": str(csv_path),
            "summary_json": str(analysis_dir / "ed_bottleneck_v1_summary.json"),
            "summary_md": str(analysis_dir / "ed_bottleneck_v1_summary.md"),
            "plot_ready_csv": str(plot_path),
        },
    }
    json_path = analysis_dir / "ed_bottleneck_v1_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# ED Bottleneck V1 Summary",
        "",
        f"- scenario_count: {summary['scenario_count']}",
        f"- valid_report_count: {summary['valid_report_count']}",
        f"- invalid_report_count: {summary['invalid_report_count']}",
        "",
        "## Interpretation",
        "",
        "- If nurse_capacity_sweep improves queue_success_rate as bedside_nurse_count increases, the bottleneck is capacity.",
        "- If service_time_multiplier improves queue_success_rate, the bottleneck is service duration.",
        "- If neither improves, move to V2 structural debugging.",
    ]
    (analysis_dir / "ed_bottleneck_v1_summary.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ED bottleneck V1 summary from existing cluster outputs.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--analysis-dir", default=str(DEFAULT_ANALYSIS_DIR))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(build_summary(args.output_root, args.analysis_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
