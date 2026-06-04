#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis"
for _path in (str(REPO_ROOT), str(ANALYSIS_DIR), str(Path(__file__).resolve().parent)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from analysis.threshold_search_report import (
    aggregate_results_by_load_factor,
    build_threshold_search_report,
    choose_threshold_candidates,
    load_hospital_profiles,
    load_threshold_search_config,
    read_csv,
    write_json,
)


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _collect_seed_results(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in matrix_rows:
        sim_dir = row.get("expected_sim_dir")
        if not sim_dir:
            continue
        sim_status = _read_json(Path(sim_dir) / "sim_status.json")
        failure_report = _read_json(Path(sim_dir) / "analysis" / "failure_report.json")
        if not sim_status and not failure_report:
            continue
        resources = dict(sim_status.get("resources") or {})
        reason_counts = dict(failure_report.get("failure_reason_counts") or resources.get("failure_reason_counts") or {})
        results.append(
            {
                "profile": row["profile"],
                "phase": row["phase"],
                "load_factor": float(row["load_factor"]),
                "preload_patient_count": int(float(row["preload_patient_count"])),
                "seed": int(float(row["seed"])),
                "target_sim": row.get("target_sim"),
                "sim_dir": sim_dir,
                "failure_rate": float(failure_report.get("failure_rate", resources.get("failure_rate", 0.0)) or 0.0),
                "failed_patients_count": int(
                    failure_report.get("failed_patients_count", resources.get("failed_patients_count", 0)) or 0
                ),
                "system_failed": bool(failure_report.get("system_failed", resources.get("system_failed", False))),
                "failure_reason_counts": reason_counts,
                "week13_failure_metrics_verify": "unknown",
            }
        )
    return results


def merge_cluster_results(config: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    fine_matrix = read_csv(config["outputs"]["cluster_fine_sweep_matrix"])
    final_matrix = read_csv(config["outputs"]["cluster_final_validation_matrix"])

    if dry_run:
        payload = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
            "mode": "dry_run",
            "fine_matrix_rows": len(fine_matrix),
            "final_matrix_rows": len(final_matrix),
            "threshold_status": "dry_run_only",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return payload

    threshold = float(config["failure_threshold"])
    fine_results = _collect_seed_results([row for row in fine_matrix if row.get("load_factor") not in ("", None)])
    final_results = _collect_seed_results([row for row in final_matrix if row.get("load_factor") not in ("", None)])
    fine_report = aggregate_results_by_load_factor(fine_results, threshold=threshold)
    final_report = aggregate_results_by_load_factor(final_results, threshold=threshold)
    threshold_candidates = choose_threshold_candidates(fine_report)

    hospital_profiles = load_hospital_profiles()
    threshold_profile = None
    threshold_load_factor = None
    threshold_preload_patient_count = None
    median_failure_rate_at_threshold = None
    fail_seed_count_at_threshold = None
    dominant_failure_reason_at_threshold = None
    threshold_status = "not_found"
    for profile, candidate in threshold_candidates.items():
        if candidate is None:
            continue
        threshold_profile = profile
        threshold_load_factor = candidate
        threshold_preload_patient_count = round(int(hospital_profiles[profile]["normal_patient_count"]) * candidate)
        for row in fine_report.get(profile, []):
            if float(row["load_factor"]) == float(candidate):
                median_failure_rate_at_threshold = row["median_failure_rate"]
                fail_seed_count_at_threshold = row["fail_seed_count"]
                dominant_failure_reason_at_threshold = row["dominant_failure_reason"]
                threshold_status = row["threshold_status"]
                break
        break

    fine_output = REPO_ROOT / "analysis" / "fine_sweep_report.json"
    final_output = REPO_ROOT / "analysis" / "final_validation_report.json"
    write_json(fine_output, fine_report)
    write_json(final_output, final_report)

    threshold_report = build_threshold_search_report(
        phase5a_status="completed",
        phase5b_status="cluster_results_merged",
        local_signal_check_summary={"status": "see_phase5a_reports"},
        local_coarse_sweep_summary={"status": "see_phase5a_reports"},
        local_bracket_status={"threshold_candidates": threshold_candidates},
        cluster_matrix_generated=True,
        cluster_fine_sweep_jobs_count=len(fine_matrix),
        cluster_final_validation_jobs_count=len([row for row in final_matrix if row.get("phase") == "final_validation"]),
        threshold_status=threshold_status,
        threshold_load_factor=threshold_load_factor,
        threshold_preload_patient_count=threshold_preload_patient_count,
        median_failure_rate_at_threshold=median_failure_rate_at_threshold,
        fail_seed_count_at_threshold=fail_seed_count_at_threshold,
        dominant_failure_reason_at_threshold=dominant_failure_reason_at_threshold,
        known_limitations=[
            "curves may be non-monotonic and should be interpreted with per-load-factor summaries",
            "full movement/environment contract mismatch remains a known limitation outside threshold math",
        ],
        next_steps=["review final_validation_report.json before publishing a threshold recommendation"],
    )
    write_json(config["outputs"]["threshold_report"], threshold_report)
    return threshold_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge cluster threshold search results.")
    parser.add_argument("--config", default=str(REPO_ROOT / "configs" / "failure_rate_threshold_search.yaml"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_threshold_search_config(args.config)
    payload = merge_cluster_results(config, dry_run=bool(args.dry_run))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
