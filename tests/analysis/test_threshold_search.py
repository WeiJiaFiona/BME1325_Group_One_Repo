import json
from pathlib import Path

from analysis.threshold_search_report import (
    build_threshold_search_report,
    classify_threshold_point,
    detect_bracket_found,
    detect_non_monotonic_points,
    generate_cluster_final_validation_matrix,
    generate_cluster_fine_sweep_matrix,
    generate_coarse_load_factors,
    generate_fine_factors_from_bracket,
    generate_signal_check_plan,
    load_hospital_profiles,
    load_threshold_search_config,
    summarize_failure_statistics,
)


ROOT = Path(__file__).resolve().parents[2]


def test_load_threshold_search_config():
    config = load_threshold_search_config(ROOT / "configs" / "failure_rate_threshold_search.yaml")
    assert config["failure_threshold"] == 0.1
    assert config["system_failed_comparator"] == "gt"
    assert config["search"]["fine_step"] == 0.05


def test_generate_signal_check_plan():
    profiles = load_hospital_profiles(ROOT / "configs" / "hospital_level_profiles.json")
    plan = generate_signal_check_plan(
        profiles=["medium_city_ed", "small_county_ed"],
        hospital_profiles=profiles,
        run_steps=100,
        seeds=[42],
    )
    assert len(plan) == 2
    assert plan[0]["run_steps"] == 100
    assert plan[0]["preload_patient_count"] == round(plan[0]["normal_patient_count"] * plan[0]["load_factor"])


def test_generate_coarse_load_factors():
    config = load_threshold_search_config(ROOT / "configs" / "failure_rate_threshold_search.yaml")
    assert generate_coarse_load_factors(config) == [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0]


def test_detect_bracket_found():
    bracket = detect_bracket_found(
        [
            {"load_factor": 1.0, "failure_rate": 0.02},
            {"load_factor": 1.2, "failure_rate": 0.08},
            {"load_factor": 1.4, "failure_rate": 0.12},
        ],
        threshold=0.1,
    )
    assert bracket["bracket_status"] == "found"
    assert bracket["last_safe"] == 1.2
    assert bracket["first_fail"] == 1.4


def test_detect_threshold_not_found():
    bracket = detect_bracket_found(
        [
            {"load_factor": 1.0, "failure_rate": 0.0},
            {"load_factor": 1.2, "failure_rate": 0.02},
            {"load_factor": 1.4, "failure_rate": 0.08},
        ],
        threshold=0.1,
    )
    assert bracket["bracket_status"] == "not_found_in_local_range"
    assert bracket["first_fail"] is None


def test_detect_below_or_at_normal_load():
    bracket = detect_bracket_found(
        [
            {"load_factor": 1.0, "failure_rate": 0.2},
            {"load_factor": 1.2, "failure_rate": 0.25},
        ],
        threshold=0.1,
    )
    assert bracket["bracket_status"] == "below_or_at_normal_load"
    assert bracket["last_safe"] is None
    assert bracket["first_fail"] == 1.0


def test_generate_fine_factors_from_bracket():
    assert generate_fine_factors_from_bracket(1.2, 1.35, fine_step=0.05) == [1.2, 1.25, 1.3, 1.35]


def test_generate_cluster_fine_sweep_matrix():
    profiles = load_hospital_profiles(ROOT / "configs" / "hospital_level_profiles.json")
    rows = generate_cluster_fine_sweep_matrix(
        brackets={"medium_city_ed": {"bracket_status": "found", "last_safe": 1.2, "first_fail": 1.3}},
        hospital_profiles=profiles,
        fine_step=0.05,
        seeds=[42, 43, 44],
        run_steps=20000,
        failure_threshold=0.1,
        system_failed_comparator="gt",
    )
    assert len(rows) == 9
    assert rows[0]["phase"] == "fine_sweep"
    assert rows[0]["run_steps"] == 20000


def test_generate_cluster_final_validation_matrix():
    profiles = load_hospital_profiles(ROOT / "configs" / "hospital_level_profiles.json")
    rows = generate_cluster_final_validation_matrix(
        threshold_candidates={"medium_city_ed": 1.3},
        hospital_profiles=profiles,
        seeds=[42, 43],
        run_steps=20000,
        failure_threshold=0.1,
        system_failed_comparator="gt",
    )
    assert len(rows) == 6
    assert {row["load_factor"] for row in rows} == {1.25, 1.3, 1.35}


def test_median_mean_min_max_fail_seed_count():
    summary = summarize_failure_statistics(
        [
            {"failure_rate": 0.05},
            {"failure_rate": 0.15},
            {"failure_rate": 0.2},
        ],
        threshold=0.1,
    )
    assert summary["median_failure_rate"] == 0.15
    assert round(summary["mean_failure_rate"], 4) == round((0.05 + 0.15 + 0.2) / 3.0, 4)
    assert summary["min_failure_rate"] == 0.05
    assert summary["max_failure_rate"] == 0.2
    assert summary["fail_seed_count"] == 2


def test_threshold_requires_median_and_fail_seed_majority():
    status = classify_threshold_point(
        {"median_failure_rate": 0.11, "fail_seed_count": 2, "num_seeds": 3},
        threshold=0.1,
    )
    assert status["threshold_status"] == "found"
    assert status["unstable_boundary"] is False


def test_unstable_boundary_detection():
    status = classify_threshold_point(
        {"median_failure_rate": 0.11, "fail_seed_count": 1, "num_seeds": 3},
        threshold=0.1,
    )
    assert status["threshold_status"] == "unstable_boundary"
    assert status["unstable_boundary"] is True


def test_non_monotonic_points_detection():
    points = detect_non_monotonic_points(
        [
            {"load_factor": 1.0, "median_failure_rate": 0.01},
            {"load_factor": 1.2, "median_failure_rate": 0.12},
            {"load_factor": 1.4, "median_failure_rate": 0.09},
        ]
    )
    assert len(points) == 1
    assert points[0]["load_factor"] == 1.4


def test_no_failure_signal_does_not_fabricate_threshold():
    summary = summarize_failure_statistics(
        [
            {"failure_rate": 0.0},
            {"failure_rate": 0.0},
            {"failure_rate": 0.0},
        ],
        threshold=0.1,
    )
    assert summary["threshold_status"] == "safe"
    assert summary["fail_seed_count"] == 0


def test_threshold_report_schema(tmp_path: Path):
    report = build_threshold_search_report(
        phase5a_status="no_failure_signal_detected",
        phase5b_status="not_ready_for_cluster_fine_sweep",
        local_signal_check_summary={"status": "no_failure_signal_detected"},
        local_coarse_sweep_summary={"status": "blocked"},
        local_bracket_status={"medium_city_ed": {"bracket_status": "not_applicable_no_failure_signal"}},
        cluster_matrix_generated=True,
        cluster_fine_sweep_jobs_count=0,
        cluster_final_validation_jobs_count=0,
        threshold_status="not_ready_for_cluster_fine_sweep",
        threshold_load_factor=None,
        threshold_preload_patient_count=None,
        median_failure_rate_at_threshold=None,
        fail_seed_count_at_threshold=None,
        dominant_failure_reason_at_threshold=None,
        known_limitations=["local signal not detected"],
        next_steps=["increase run steps"],
    )
    out = tmp_path / "threshold_search_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    payload = json.loads(out.read_text(encoding="utf-8"))
    for key in (
        "phase5a_status",
        "phase5b_status",
        "local_signal_check_summary",
        "local_coarse_sweep_summary",
        "local_bracket_status",
        "cluster_matrix_generated",
        "cluster_fine_sweep_jobs_count",
        "cluster_final_validation_jobs_count",
        "threshold_status",
        "known_limitations",
        "next_steps",
    ):
        assert key in payload
