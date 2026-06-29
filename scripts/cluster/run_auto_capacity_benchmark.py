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
DEFAULT_SCENARIO_CSV = REPO_ROOT / "configs" / "cluster" / "auto_capacity_cn_benchmark_scenarios.csv"
DEFAULT_RAW_OUTPUT_ROOT = REPO_ROOT / "cluster_outputs" / "large_tertiary_ed_300_capacity_benchmark_raw"
DEFAULT_BENCHMARK_OUTPUT_ROOT = REPO_ROOT / "test_results" / "auto_capacity_large_tertiary_final"
PILOT_RUN_IDS = ["A_LOAD_1p00_seed42", "B_BURST_120_seed42", "C_CRIT_60_seed42"]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row_index_by_run_id(rows: list[dict[str, str]]) -> dict[str, int]:
    return {str(row.get("scenario_id") or row.get("benchmark_run_id")): idx for idx, row in enumerate(rows, start=1)}


def ensure_scenarios(path: Path) -> None:
    if path.exists():
        return
    subprocess.run(
        [sys.executable, "scripts/cluster/build_auto_capacity_benchmark_scenarios.py", "--output", str(path)],
        cwd=str(REPO_ROOT),
        check=True,
    )


def run_raw_scenario(
    *,
    scenario_csv: Path,
    row_index: int,
    raw_output_root: Path,
    backend_only: bool,
    dry_run: bool,
) -> None:
    cmd = [
        sys.executable,
        "scripts/cluster/run_one_ed_bottleneck_v1_scenario.py",
        "--scenario-csv",
        str(scenario_csv),
        "--row-index",
        str(row_index),
        "--output-root",
        str(raw_output_root),
    ]
    if backend_only:
        cmd.append("--backend-only")
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
    env.setdefault("EDSIM_BEDSIDE_QUEUE_SCAN_TELEMETRY", "1")
    subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=True)


def export_runs(*, scenario_csv: Path, raw_output_root: Path, benchmark_output_root: Path, run_ids: list[str]) -> None:
    cmd = [
        sys.executable,
        "analysis/auto_capacity_benchmark_export.py",
        "--scenario-csv",
        str(scenario_csv),
        "--raw-output-root",
        str(raw_output_root),
        "--benchmark-output-root",
        str(benchmark_output_root),
    ]
    for run_id in run_ids:
        cmd.extend(["--run-id", run_id])
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EDMAS Auto Mode capacity benchmark.")
    parser.add_argument("--scenario-csv", default=str(DEFAULT_SCENARIO_CSV))
    parser.add_argument("--raw-output-root", default=str(DEFAULT_RAW_OUTPUT_ROOT))
    parser.add_argument("--benchmark-output-root", default=str(DEFAULT_BENCHMARK_OUTPUT_ROOT))
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--pilot", action="store_true", help="Run A_LOAD_1p00_seed42, B_BURST_120_seed42, C_CRIT_60_seed42.")
    parser.add_argument("--run-all", action="store_true", help="Run all scenario rows.")
    parser.add_argument("--run-id", action="append", default=None, help="Run one scenario id; repeatable.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-export", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_csv = Path(args.scenario_csv)
    raw_output_root = Path(args.raw_output_root)
    benchmark_output_root = Path(args.benchmark_output_root)
    ensure_scenarios(scenario_csv)
    if args.build_only:
        print(json.dumps({"scenario_csv": str(scenario_csv), "status": "built"}, indent=2))
        return

    rows = load_rows(scenario_csv)
    indexes = row_index_by_run_id(rows)
    if args.run_all:
        run_ids = [str(row["scenario_id"]) for row in rows]
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
            backend_only=True,
            dry_run=bool(args.dry_run),
        )
    if not args.skip_export and not args.dry_run:
        export_runs(
            scenario_csv=scenario_csv,
            raw_output_root=raw_output_root,
            benchmark_output_root=benchmark_output_root,
            run_ids=run_ids,
        )
    print(json.dumps({"selected_runs": run_ids, "dry_run": bool(args.dry_run)}, indent=2))


if __name__ == "__main__":
    main()
