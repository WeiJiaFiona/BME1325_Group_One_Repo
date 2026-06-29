#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _mean_bool(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if _bool(row.get("pia_sdr_success"))) / float(len(rows))


def _ctas_mix(rows: list[dict[str, Any]]) -> dict[str, float]:
    counts = {f"L{i}": 0 for i in range(1, 6)}
    total = 0
    for row in rows:
        ctas = str(row.get("ctas_level") or "").strip()
        if ctas in counts:
            counts[ctas] += 1
            total += 1
    return {key: (value / total if total else 0.0) for key, value in counts.items()}


def validate_run(run_dir: Path) -> dict[str, Any]:
    required = {
        "scenario_config": run_dir / "scenario_config.json",
        "patient_level_results": run_dir / "patient_level_results.csv",
        "capacity_timeseries": run_dir / "capacity_timeseries.csv",
        "run_summary": run_dir / "run_summary.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    scenario = _load_json(required["scenario_config"]) if required["scenario_config"].exists() else {}
    summary = _load_json(required["run_summary"]) if required["run_summary"].exists() else {}
    patients = _read_csv(required["patient_level_results"])
    timeseries = _read_csv(required["capacity_timeseries"])

    overall_rows = [row for row in patients if str(row.get("ctas_level") or "").strip()]
    critical_rows = [row for row in overall_rows if row.get("ctas_level") in {"L1", "L2"}]
    recomputed_overall = _mean_bool(overall_rows)
    recomputed_critical = _mean_bool(critical_rows)
    recomputed_by_ctas = {
        f"L{i}": _mean_bool([row for row in overall_rows if row.get("ctas_level") == f"L{i}"])
        for i in range(1, 6)
    }

    summary_by_ctas = summary.get("sdr_by_ctas") if isinstance(summary.get("sdr_by_ctas"), dict) else {}
    warnings: list[str] = []
    failures: list[str] = []
    if missing:
        failures.append("missing_required_files")
    expected_arrivals = int(scenario.get("actual_simulated_arrivals") or 0)
    if expected_arrivals and patients:
        ratio = len(patients) / float(expected_arrivals)
        if ratio < 0.8 or ratio > 1.25:
            warnings.append("patient_count_not_close_to_actual_simulated_arrivals")
    if recomputed_overall is not None and _num(summary.get("overall_sdr")) is not None:
        if abs(float(summary["overall_sdr"]) - recomputed_overall) > 1e-9:
            failures.append("overall_sdr_not_recomputable")
    if recomputed_critical is not None and _num(summary.get("critical_sdr")) is not None:
        if abs(float(summary["critical_sdr"]) - recomputed_critical) > 1e-9:
            failures.append("critical_sdr_not_recomputable")
    for ctas, value in recomputed_by_ctas.items():
        summary_value = _num(summary_by_ctas.get(ctas))
        if value is not None and summary_value is not None and abs(summary_value - value) > 1e-9:
            failures.append(f"sdr_by_ctas_{ctas}_not_recomputable")
    if not timeseries:
        failures.append("capacity_timeseries_empty")
    if patients and sum(1 for row in patients if row.get("first_doctor_contact_minute") in (None, "")) > len(patients) * 0.5:
        warnings.append("large_no_doctor_contact_count")

    report = {
        "run_id": scenario.get("run_id") or run_dir.name,
        "run_dir": str(run_dir),
        "required_files": {name: path.exists() for name, path in required.items()},
        "patient_count": len(patients),
        "actual_simulated_arrivals": expected_arrivals,
        "patient_count_close_to_expected": not any(w == "patient_count_not_close_to_actual_simulated_arrivals" for w in warnings),
        "overall_sdr_recomputed": recomputed_overall,
        "critical_sdr_recomputed": recomputed_critical,
        "sdr_by_ctas_recomputed": recomputed_by_ctas,
        "ctas_mix_observed": _ctas_mix(patients),
        "timeseries_rows": len(timeseries),
        "failures": failures,
        "warnings": warnings,
        "validation_status": "ok" if not failures else "failed",
    }
    (run_dir / "validator_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate one or more large tertiary benchmark runs.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", action="append", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.output_root)
    run_dirs = [root / run_id for run_id in args.run_id] if args.run_id else [p for p in root.iterdir() if p.is_dir() and p.name != "aggregate"]
    reports = [validate_run(run_dir) for run_dir in run_dirs if run_dir.exists()]
    print(json.dumps({"validated": [r["run_id"] for r in reports], "count": len(reports)}, indent=2))


if __name__ == "__main__":
    main()
