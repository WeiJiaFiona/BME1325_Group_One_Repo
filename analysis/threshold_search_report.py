from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "failure_rate_threshold_search.yaml"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "analysis" / "threshold_search_report.json"

SIGNAL_CHECK_DEFAULTS = {
    "medium_city_ed": 2.0,
    "small_county_ed": 3.0,
}


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def load_threshold_search_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    payload.setdefault("failure_threshold", 0.1)
    payload.setdefault("system_failed_comparator", "gt")
    payload.setdefault("profiles", ["medium_city_ed", "small_county_ed"])
    payload.setdefault("outputs", {})
    payload.setdefault("phase5a", {})
    payload.setdefault("phase5b", {})

    search = payload.setdefault("search", {})
    search.setdefault("method", "coarse_to_fine")
    search.setdefault("coarse_load_factors", [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0])
    search.setdefault("fine_step", 0.05)
    search.setdefault("min_load_factor", 1.0)
    search.setdefault("max_load_factor", 3.0)
    search.setdefault("aggregation", "median_failure_rate")
    search.setdefault("local_signal_seeds", [42])
    search.setdefault("cluster_fine_seeds", [42, 43, 44])
    search.setdefault("cluster_final_validation_seeds", [42, 43, 44, 45, 46, 47, 48, 49, 50, 51])
    search.setdefault("cluster_run_steps", 20000)
    payload["outputs"].setdefault("threshold_report", "analysis/threshold_search_report.json")
    payload["outputs"].setdefault("local_signal_check_report", "analysis/local_signal_check_report.json")
    payload["outputs"].setdefault("local_preliminary_coarse_sweep_report", "analysis/local_preliminary_coarse_sweep_report.json")
    payload["outputs"].setdefault("local_bracket_report", "analysis/local_bracket_report.json")
    payload["outputs"].setdefault("cluster_fine_sweep_matrix", "configs/cluster_fine_sweep_matrix.csv")
    payload["outputs"].setdefault("cluster_final_validation_matrix", "configs/cluster_final_validation_matrix.csv")
    payload["outputs"].setdefault("trigger_audit", "docs/week13_failure_reason_trigger_audit.md")
    payload["outputs"].setdefault("phase5_summary", "docs/week13_phase5_two_stage_threshold_search_summary.md")
    return payload


def load_hospital_profiles(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else REPO_ROOT / "configs" / "hospital_level_profiles.json"
    return json.loads(target.read_text(encoding="utf-8"))


def generate_signal_check_plan(
    *,
    profiles: list[str],
    hospital_profiles: dict[str, Any],
    run_steps: int,
    seeds: list[int],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for profile in profiles:
        profile_meta = hospital_profiles[profile]
        load_factor = float(SIGNAL_CHECK_DEFAULTS.get(profile, profile_meta.get("load_factors", [1.0])[-1]))
        normal_patient_count = int(profile_meta["normal_patient_count"])
        for seed in seeds:
            plan.append(
                {
                    "hospital_profile": profile,
                    "doctor_count": int(profile_meta["doctor_count"]),
                    "nurse_count": int(profile_meta["nurse_count"]),
                    "normal_patient_count": normal_patient_count,
                    "load_factor": load_factor,
                    "preload_patient_count": round(normal_patient_count * load_factor),
                    "arrival_profile_mode": "normal",
                    "background_arrival_enabled": False,
                    "boarding_profile": "baseline",
                    "ctas_distribution": "fixed_default",
                    "seed": int(seed),
                    "run_steps": int(run_steps),
                }
            )
    return plan


def generate_coarse_load_factors(config: dict[str, Any]) -> list[float]:
    return [float(value) for value in config["search"]["coarse_load_factors"]]


def generate_coarse_sweep_plan(
    *,
    profiles: list[str],
    hospital_profiles: dict[str, Any],
    load_factors: list[float],
    run_steps: int,
    seeds: list[int],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for profile in profiles:
        profile_meta = hospital_profiles[profile]
        normal_patient_count = int(profile_meta["normal_patient_count"])
        for load_factor in load_factors:
            for seed in seeds:
                plan.append(
                    {
                        "hospital_profile": profile,
                        "doctor_count": int(profile_meta["doctor_count"]),
                        "nurse_count": int(profile_meta["nurse_count"]),
                        "normal_patient_count": normal_patient_count,
                        "load_factor": float(load_factor),
                        "preload_patient_count": round(normal_patient_count * float(load_factor)),
                        "arrival_profile_mode": "normal",
                        "background_arrival_enabled": False,
                        "boarding_profile": "baseline",
                        "ctas_distribution": "fixed_default",
                        "seed": int(seed),
                        "run_steps": int(run_steps),
                    }
                )
    return plan


def has_failure_signal(result: dict[str, Any]) -> bool:
    failure_rate = float(result.get("failure_rate", 0.0) or 0.0)
    if failure_rate > 0.0:
        return True
    reason_counts = dict(result.get("failure_reason_counts") or {})
    if any(int(value or 0) > 0 for value in reason_counts.values()):
        return True
    return bool(result.get("system_failed", False))


def determine_signal_check_status(results: list[dict[str, Any]]) -> str:
    return "signal_detected" if any(has_failure_signal(row) for row in results) else "no_failure_signal_detected"


def detect_bracket_found(rows: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: float(row["load_factor"]))
    if not ordered:
        return {"bracket_status": "not_found_in_local_range", "last_safe": None, "first_fail": None}

    first = ordered[0]
    if float(first.get("failure_rate", 0.0) or 0.0) > threshold:
        return {
            "bracket_status": "below_or_at_normal_load",
            "last_safe": None,
            "first_fail": float(first["load_factor"]),
        }

    last_safe = None
    first_fail = None
    for row in ordered:
        load_factor = float(row["load_factor"])
        failure_rate = float(row.get("failure_rate", 0.0) or 0.0)
        if failure_rate <= threshold:
            last_safe = load_factor
        elif first_fail is None:
            first_fail = load_factor
            break

    if last_safe is not None and first_fail is not None:
        return {
            "bracket_status": "found",
            "last_safe": float(last_safe),
            "first_fail": float(first_fail),
            "bracket": [float(last_safe), float(first_fail)],
        }

    return {"bracket_status": "not_found_in_local_range", "last_safe": float(last_safe) if last_safe is not None else None, "first_fail": None}


def detect_local_brackets(results: list[dict[str, Any]], *, threshold: float) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        grouped.setdefault(str(row["profile"]), []).append(row)
    return {profile: detect_bracket_found(rows, threshold=threshold) for profile, rows in grouped.items()}


def generate_fine_factors_from_bracket(last_safe: float, first_fail: float, *, fine_step: float) -> list[float]:
    values: list[float] = []
    current = float(last_safe)
    while current <= float(first_fail) + 1e-9:
        values.append(round(current, 4))
        current += float(fine_step)
    if values[-1] != round(float(first_fail), 4):
        values.append(round(float(first_fail), 4))
    return values


def build_target_sim_name(profile: str, phase: str, load_factor: float, seed: int) -> str:
    factor_label = str(load_factor).replace(".", "p")
    return f"week13_{phase}_{profile}_lf_{factor_label}_seed{seed}"


def generate_cluster_fine_sweep_matrix(
    *,
    brackets: dict[str, dict[str, Any]],
    hospital_profiles: dict[str, Any],
    fine_step: float,
    seeds: list[int],
    run_steps: int,
    failure_threshold: float,
    system_failed_comparator: str,
    origin: str = "ed_sim_n5",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    job_index = 1
    for profile in sorted(brackets):
        bracket = brackets[profile]
        if bracket.get("bracket_status") != "found":
            continue
        normal_patient_count = int(hospital_profiles[profile]["normal_patient_count"])
        factors = generate_fine_factors_from_bracket(
            float(bracket["last_safe"]),
            float(bracket["first_fail"]),
            fine_step=fine_step,
        )
        for load_factor in factors:
            preload_patient_count = round(normal_patient_count * float(load_factor))
            for seed in seeds:
                target_sim = build_target_sim_name(profile, "fine_sweep", load_factor, int(seed))
                expected_sim_dir = REPO_ROOT / "environment" / "frontend_server" / "storage" / target_sim
                rows.append(
                    {
                        "job_id": f"fine_{job_index:04d}",
                        "profile": profile,
                        "phase": "fine_sweep",
                        "load_factor": float(load_factor),
                        "preload_patient_count": int(preload_patient_count),
                        "seed": int(seed),
                        "run_steps": int(run_steps),
                        "origin": origin,
                        "target_sim": target_sim,
                        "failure_threshold": float(failure_threshold),
                        "system_failed_comparator": system_failed_comparator,
                        "expected_sim_dir": str(expected_sim_dir),
                        "expected_failure_report_path": str(expected_sim_dir / "analysis" / "failure_report.json"),
                    }
                )
                job_index += 1
    return rows


def generate_cluster_final_validation_matrix(
    *,
    threshold_candidates: dict[str, float | None],
    hospital_profiles: dict[str, Any],
    seeds: list[int],
    run_steps: int,
    failure_threshold: float,
    system_failed_comparator: str,
    origin: str = "ed_sim_n5",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    job_index = 1
    for profile in sorted(threshold_candidates):
        candidate = threshold_candidates[profile]
        if candidate is None:
            rows.append(
                {
                    "job_id": f"final_{job_index:04d}",
                    "profile": profile,
                    "phase": "final_validation_placeholder",
                    "load_factor": None,
                    "preload_patient_count": None,
                    "seed": None,
                    "run_steps": int(run_steps),
                    "origin": origin,
                    "target_sim": None,
                    "failure_threshold": float(failure_threshold),
                    "system_failed_comparator": system_failed_comparator,
                    "expected_sim_dir": None,
                    "expected_failure_report_path": None,
                    "final_validation_status": "waiting_for_cluster_fine_sweep",
                }
            )
            job_index += 1
            continue

        normal_patient_count = int(hospital_profiles[profile]["normal_patient_count"])
        factors = [round(candidate - 0.05, 4), round(candidate, 4), round(candidate + 0.05, 4)]
        for load_factor in factors:
            preload_patient_count = round(normal_patient_count * float(load_factor))
            for seed in seeds:
                target_sim = build_target_sim_name(profile, "final_validation", load_factor, int(seed))
                expected_sim_dir = REPO_ROOT / "environment" / "frontend_server" / "storage" / target_sim
                rows.append(
                    {
                        "job_id": f"final_{job_index:04d}",
                        "profile": profile,
                        "phase": "final_validation",
                        "load_factor": float(load_factor),
                        "preload_patient_count": int(preload_patient_count),
                        "seed": int(seed),
                        "run_steps": int(run_steps),
                        "origin": origin,
                        "target_sim": target_sim,
                        "failure_threshold": float(failure_threshold),
                        "system_failed_comparator": system_failed_comparator,
                        "expected_sim_dir": str(expected_sim_dir),
                        "expected_failure_report_path": str(expected_sim_dir / "analysis" / "failure_report.json"),
                        "final_validation_status": "ready",
                    }
                )
                job_index += 1
    return rows


def summarize_failure_statistics(results: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    rates = [float(row.get("failure_rate", 0.0) or 0.0) for row in results]
    if not rates:
        return {
            "median_failure_rate": None,
            "mean_failure_rate": None,
            "min_failure_rate": None,
            "max_failure_rate": None,
            "fail_seed_count": 0,
            "num_seeds": 0,
            "threshold_status": "safe",
            "unstable_boundary": False,
        }
    fail_seed_count = sum(1 for rate in rates if rate > threshold)
    num_seeds = len(rates)
    summary = {
        "median_failure_rate": float(median(rates)),
        "mean_failure_rate": float(mean(rates)),
        "min_failure_rate": float(min(rates)),
        "max_failure_rate": float(max(rates)),
        "fail_seed_count": int(fail_seed_count),
        "num_seeds": int(num_seeds),
    }
    summary.update(classify_threshold_point(summary, threshold=threshold))
    return summary


def classify_threshold_point(summary: dict[str, Any], *, threshold: float) -> dict[str, Any]:
    median_failure_rate = summary.get("median_failure_rate")
    fail_seed_count = int(summary.get("fail_seed_count", 0) or 0)
    num_seeds = int(summary.get("num_seeds", 0) or 0)
    majority = int(math.ceil(num_seeds / 2.0)) if num_seeds else 0
    if median_failure_rate is None:
        return {"threshold_status": "safe", "unstable_boundary": False}
    if float(median_failure_rate) > threshold and fail_seed_count >= majority:
        return {"threshold_status": "found", "unstable_boundary": False}
    if float(median_failure_rate) > threshold and fail_seed_count < majority:
        return {"threshold_status": "unstable_boundary", "unstable_boundary": True}
    return {"threshold_status": "safe", "unstable_boundary": False}


def detect_non_monotonic_points(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: float(row["load_factor"]))
    non_monotonic: list[dict[str, Any]] = []
    peak = -1.0
    previous_rate = None
    previous_factor = None
    for row in ordered:
        factor = float(row["load_factor"])
        rate = float(row.get("median_failure_rate", row.get("failure_rate", 0.0)) or 0.0)
        if previous_rate is not None and rate + 1e-9 < peak:
            non_monotonic.append(
                {
                    "load_factor": factor,
                    "failure_rate": rate,
                    "previous_load_factor": previous_factor,
                    "previous_failure_rate": previous_rate,
                }
            )
        peak = max(peak, rate)
        previous_rate = rate
        previous_factor = factor
    return non_monotonic


def choose_threshold_candidates(fine_sweep_summary: dict[str, list[dict[str, Any]]]) -> dict[str, float | None]:
    candidates: dict[str, float | None] = {}
    for profile, rows in fine_sweep_summary.items():
        candidate = None
        for row in sorted(rows, key=lambda item: float(item["load_factor"])):
            if row.get("threshold_status") == "found":
                candidate = float(row["load_factor"])
                break
        candidates[profile] = candidate
    return candidates


def aggregate_results_by_load_factor(
    seed_results: list[dict[str, Any]],
    *,
    threshold: float,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[float, list[dict[str, Any]]]] = {}
    for row in seed_results:
        profile = str(row["profile"])
        factor = float(row["load_factor"])
        grouped.setdefault(profile, {}).setdefault(factor, []).append(row)

    aggregated: dict[str, list[dict[str, Any]]] = {}
    for profile, by_factor in grouped.items():
        profile_rows: list[dict[str, Any]] = []
        for factor, results in sorted(by_factor.items()):
            summary = summarize_failure_statistics(results, threshold=threshold)
            dominant_counts: dict[str, int] = {}
            for result in results:
                for reason, count in dict(result.get("failure_reason_counts") or {}).items():
                    dominant_counts[reason] = dominant_counts.get(reason, 0) + int(count or 0)
            dominant_reason = None
            if any(count > 0 for count in dominant_counts.values()):
                dominant_reason = max(sorted(dominant_counts), key=lambda key: dominant_counts[key])
            profile_rows.append(
                {
                    "profile": profile,
                    "load_factor": factor,
                    "preload_patient_count": int(results[0]["preload_patient_count"]),
                    "seed_results": results,
                    "dominant_failure_reason": dominant_reason,
                    **summary,
                }
            )
        non_monotonic = detect_non_monotonic_points(profile_rows)
        for row in profile_rows:
            row["non_monotonic_points"] = non_monotonic
        aggregated[profile] = profile_rows
    return aggregated


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build_threshold_search_report(
    *,
    phase5a_status: str,
    phase5b_status: str,
    local_signal_check_summary: dict[str, Any],
    local_coarse_sweep_summary: dict[str, Any],
    local_bracket_status: dict[str, Any],
    cluster_matrix_generated: bool,
    cluster_fine_sweep_jobs_count: int,
    cluster_final_validation_jobs_count: int,
    threshold_status: str,
    threshold_load_factor: float | None,
    threshold_preload_patient_count: int | None,
    median_failure_rate_at_threshold: float | None,
    fail_seed_count_at_threshold: int | None,
    dominant_failure_reason_at_threshold: str | None,
    known_limitations: list[str],
    next_steps: list[str],
) -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "phase5a_status": phase5a_status,
        "phase5b_status": phase5b_status,
        "local_signal_check_summary": local_signal_check_summary,
        "local_coarse_sweep_summary": local_coarse_sweep_summary,
        "local_bracket_status": local_bracket_status,
        "cluster_matrix_generated": cluster_matrix_generated,
        "cluster_fine_sweep_jobs_count": int(cluster_fine_sweep_jobs_count),
        "cluster_final_validation_jobs_count": int(cluster_final_validation_jobs_count),
        "threshold_status": threshold_status,
        "threshold_load_factor": threshold_load_factor,
        "threshold_preload_patient_count": threshold_preload_patient_count,
        "median_failure_rate_at_threshold": median_failure_rate_at_threshold,
        "fail_seed_count_at_threshold": fail_seed_count_at_threshold,
        "dominant_failure_reason_at_threshold": dominant_failure_reason_at_threshold,
        "known_limitations": known_limitations,
        "next_steps": next_steps,
    }
