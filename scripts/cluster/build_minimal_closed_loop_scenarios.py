#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CSV = REPO_ROOT / "configs" / "cluster" / "auto_capacity_cn_benchmark_scenarios.csv"
DEFAULT_OUTPUT = REPO_ROOT / "configs" / "cluster" / "auto_capacity_minimal_closed_loop_v1.csv"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row["scenario_id"]): dict(row) for row in rows}


def make_v0_row(base: dict[str, str], scenario_id: str) -> dict[str, str]:
    row = dict(base)
    row["scenario_id"] = scenario_id
    row["benchmark_run_id"] = scenario_id
    row["notes"] = (row.get("notes") or "") + " | minimal_closed_loop_v1 current-code V0_R0_FIXBASE"
    return row


def make_v2_row(base: dict[str, str], scenario_id: str, *, run_steps: int) -> dict[str, str]:
    row = dict(base)
    row["scenario_id"] = scenario_id
    row["benchmark_run_id"] = scenario_id
    row["run_steps"] = str(run_steps)
    row["doctor_count"] = "20"
    row["triage_nurse_count"] = "6"
    row["bedside_nurse_count"] = "24"
    row["nurse_count_total"] = "30"
    row["physicians"] = "20"
    row["triage_nurses"] = "6"
    row["bedside_nurses"] = "24"
    row["notes"] = (row.get("notes") or "") + " | minimal_closed_loop_v1 V2_R1_DOC20_TRI6_BED24"
    return row


def build_rows() -> tuple[list[dict[str, str]], list[str]]:
    rows = load_rows(SOURCE_CSV)
    by_id = row_by_id(rows)
    fieldnames = list(rows[0].keys())

    selected: list[dict[str, str]] = []
    selected.append(make_v0_row(by_id["A_LOAD_1p00_seed42"], "A_LOAD_1p00_V0_R0_FIXBASE_seed42"))
    selected.append(make_v0_row(by_id["B_BURST_120_seed42"], "B_BURST_120_V0_R0_FIXBASE_seed42"))
    selected.append(make_v0_row(by_id["C_CRIT_60_seed42"], "C_CRIT_60_V0_R0_FIXBASE_seed42"))

    selected.append(make_v2_row(by_id["A_LOAD_1p00_seed42"], "A_LOAD_1p00_V2_R1_DOC20_TRI6_BED24_SMOKE_seed42", run_steps=180))
    selected.append(make_v2_row(by_id["A_LOAD_1p00_seed42"], "A_LOAD_1p00_V2_R1_DOC20_TRI6_BED24_seed42", run_steps=1440))
    selected.append(make_v2_row(by_id["B_BURST_120_seed42"], "B_BURST_120_V2_R1_DOC20_TRI6_BED24_seed42", run_steps=1440))
    selected.append(make_v2_row(by_id["C_CRIT_60_seed42"], "C_CRIT_60_V2_R1_DOC20_TRI6_BED24_seed42", run_steps=1440))
    return selected, fieldnames


def write_rows(rows: list[dict[str, str]], fieldnames: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    rows, fieldnames = build_rows()
    output = Path(args.output)
    write_rows(rows, fieldnames, output)
    print(json.dumps({"output": str(output), "scenario_count": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
