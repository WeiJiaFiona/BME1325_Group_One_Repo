#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO_CSV = REPO_ROOT / "configs" / "benchmark" / "large_tertiary_ed_25run_matrix.csv"
DEFAULT_RAW_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "large_tertiary_ed_300_capacity_benchmark_raw"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "test_results" / "auto_capacity_large_tertiary_final"
PILOT_RUN_IDS = ["A_LOAD_1p00_seed42", "B_BURST_120_seed42", "C_CRIT_60_seed42"]


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=True)


def ensure_matrix(path: Path) -> None:
    if path.exists():
        return
    _run([sys.executable, "scripts/cluster/build_large_tertiary_capacity_benchmark.py", "--output", str(path)])


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row_index_by_run_id(rows: list[dict[str, str]]) -> dict[str, int]:
    return {str(row["scenario_id"]): idx for idx, row in enumerate(rows, start=1)}


def run_raw_scenario(*, scenario_csv: Path, row_index: int, raw_output_root: Path, dry_run: bool) -> None:
    cmd = [
        sys.executable,
        "scripts/cluster/run_one_ed_bottleneck_v1_scenario.py",
        "--scenario-csv",
        str(scenario_csv),
        "--row-index",
        str(row_index),
        "--output-root",
        str(raw_output_root),
        "--backend-only",
    ]
    if dry_run:
        cmd.append("--dry-run")
    env = os.environ.copy()
    env.setdefault("EDSIM_ROTATE_BEDSIDE_NURSE_ORDER", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    _run(cmd, env=env)


def export_runs(*, scenario_csv: Path, raw_output_root: Path, output_root: Path, run_ids: list[str]) -> None:
    cmd = [
        sys.executable,
        "analysis/large_tertiary_benchmark_exporter.py",
        "--scenario-csv",
        str(scenario_csv),
        "--raw-output-root",
        str(raw_output_root),
        "--output-root",
        str(output_root),
    ]
    for run_id in run_ids:
        cmd.extend(["--run-id", run_id])
    _run(cmd)


def validate_runs(*, output_root: Path, run_ids: list[str]) -> None:
    cmd = [sys.executable, "analysis/large_tertiary_benchmark_validator.py", "--output-root", str(output_root)]
    for run_id in run_ids:
        cmd.extend(["--run-id", run_id])
    _run(cmd)


def audit_runs(*, output_root: Path, run_ids: list[str]) -> None:
    cmd = [sys.executable, "analysis/large_tertiary_bottleneck_audit.py", "--output-root", str(output_root)]
    for run_id in run_ids:
        cmd.extend(["--run-id", run_id])
    _run(cmd)


def aggregate(output_root: Path) -> None:
    _run([sys.executable, "analysis/large_tertiary_aggregate_exporter.py", "--output-root", str(output_root)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run large tertiary ED capacity benchmark.")
    parser.add_argument("--scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--raw-output-root", default=str(DEFAULT_RAW_OUTPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--run-all", action="store_true")
    parser.add_argument("--run-id", action="append", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--validate-each", action="store_true")
    parser.add_argument("--audit-bottleneck-each", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_csv = Path(args.scenario_csv)
    raw_output_root = Path(args.raw_output_root)
    output_root = Path(args.output_root)
    ensure_matrix(scenario_csv)
    if args.build_only:
        rows = load_rows(scenario_csv)
        print(json.dumps({"scenario_csv": str(scenario_csv), "scenario_count": len(rows), "status": "built"}, indent=2))
        return

    rows = load_rows(scenario_csv)
    indexes = row_index_by_run_id(rows)
    if args.run_all:
        run_ids = [row["scenario_id"] for row in rows]
    elif args.run_id:
        run_ids = list(args.run_id)
    else:
        run_ids = PILOT_RUN_IDS if args.pilot else []
    if not run_ids:
        raise SystemExit("No runs selected. Use --pilot, --run-all, or --run-id.")
    missing = [run_id for run_id in run_ids if run_id not in indexes]
    if missing:
        raise SystemExit(f"Unknown run id(s): {', '.join(missing)}")

    for run_id in run_ids:
        run_raw_scenario(
            scenario_csv=scenario_csv,
            row_index=indexes[run_id],
            raw_output_root=raw_output_root,
            dry_run=bool(args.dry_run),
        )
        if not args.dry_run and not args.skip_export:
            export_runs(scenario_csv=scenario_csv, raw_output_root=raw_output_root, output_root=output_root, run_ids=[run_id])
            if args.validate_each:
                validate_runs(output_root=output_root, run_ids=[run_id])
            if args.audit_bottleneck_each:
                audit_runs(output_root=output_root, run_ids=[run_id])
    if not args.dry_run and not args.skip_export:
        aggregate(output_root)
    print(json.dumps({"selected_runs": run_ids, "dry_run": bool(args.dry_run)}, indent=2))


if __name__ == "__main__":
    main()
