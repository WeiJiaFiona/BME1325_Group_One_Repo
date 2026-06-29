#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.auto_capacity_benchmark_export import export_run
from analysis.large_tertiary_benchmark_validator import validate_run
from analysis.large_tertiary_bottleneck_audit import audit_run


DEFAULT_SCENARIO_CSV = REPO_ROOT / "configs" / "benchmark" / "large_tertiary_ed_25run_matrix.csv"
DEFAULT_RAW_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "large_tertiary_ed_300_capacity_benchmark_raw"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "test_results" / "auto_capacity_large_tertiary_final"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _filter_rows(rows: list[dict[str, Any]], run_ids: set[str] | None) -> list[dict[str, Any]]:
    if run_ids is None:
        return rows
    return [row for row in rows if str(row.get("scenario_id")) in run_ids]


def export_large_run(row: dict[str, Any], raw_root: Path, output_root: Path) -> dict[str, Any]:
    summary = export_run(row, raw_root, output_root)
    run_dir = output_root / str(row["scenario_id"])
    validation = validate_run(run_dir)
    bottleneck = audit_run(run_dir)
    return {
        **summary,
        "validation_status": validation.get("validation_status"),
        "bottleneck_audit": bottleneck,
    }


def export_many(rows: list[dict[str, Any]], raw_root: Path, output_root: Path) -> list[dict[str, Any]]:
    output_root.mkdir(parents=True, exist_ok=True)
    summaries = [export_large_run(row, raw_root, output_root) for row in rows]
    return summaries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export large tertiary benchmark run artifacts.")
    parser.add_argument("--scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--raw-output-root", default=str(DEFAULT_RAW_OUTPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", action="append", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = _load_rows(Path(args.scenario_csv))
    selected = _filter_rows(rows, set(args.run_id) if args.run_id else None)
    summaries = export_many(selected, Path(args.raw_output_root), Path(args.output_root))
    print(json.dumps({"exported": [s.get("run_id") for s in summaries], "count": len(summaries)}, indent=2))


if __name__ == "__main__":
    main()
