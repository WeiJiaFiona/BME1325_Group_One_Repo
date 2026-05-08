import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_week7_long_regression.py"
SPEC = importlib.util.spec_from_file_location("run_week7_long_regression", SCRIPT_PATH)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


class FixedDateTime:
    @classmethod
    def now(cls):
        import datetime as _dt

        return _dt.datetime(2024, 1, 2, 3, 4, 5)


def make_result(scenario, *, steps, expected_steps, passed=True):
    return {
        "scenario": scenario,
        "returncode": 0 if passed else 1,
        "error": None if passed else "backend exited early",
        "fail_safe_triggered": False,
        "curl_failed": False,
        "samples": [{"observed_step": steps}],
        "expected_total_steps": expected_steps,
        "sample_summary": {
            "max_current_patients": steps,
            "max_doctor_global_queue": max(0, steps - 1),
            "max_triage_queue": 1,
            "max_imaging_waiting": 0,
            "max_boarding_timeout_events": 0,
        },
        "meta_updates": {"seed": 1337},
        "final_status": {"current_patients": 2} if passed else {},
    }


def test_configure_smoke_scenario_overrides_chunk_count():
    config = {"chunk_steps": 2, "chunks": 12}

    smoke = runner.configure_smoke_scenario(config, smoke_steps=7)

    assert smoke["chunks"] == 4
    assert smoke["smoke_target_steps"] == 7
    assert config["chunks"] == 12


def test_auto_mode_stops_before_deep_when_smoke_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "SCENARIO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "datetime", FixedDateTime)

    calls = []

    def fake_run_single_scenario(name, config, report_dir, **kwargs):
        calls.append((name, report_dir.name, dict(config)))
        return make_result(name, steps=3, expected_steps=config["chunk_steps"] * config["chunks"], passed=False)

    monkeypatch.setattr(runner, "run_single_scenario", fake_run_single_scenario)

    args = SimpleNamespace(
        scenario="boarding_timeout",
        mode="auto",
        max_chunks=None,
        smoke_steps=7,
        skip_smoke=False,
        execution_profile="deep_fast",
        llm_mode=None,
        embedding_mode=None,
        seed=1337,
    )

    exit_code, summary, run_dir = runner.run_regression_flow(args)

    assert exit_code == 1
    assert summary["smoke_passed"] is False
    assert summary["deep_started"] is False
    assert summary["deep_results"] == []
    assert "boarding_timeout" in summary["smoke_failed_reason"]
    assert calls == [("boarding_timeout", "smoke", calls[0][2])]
    assert (run_dir / "summary.json").exists()


def test_auto_mode_runs_deep_after_smoke_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "SCENARIO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "datetime", FixedDateTime)

    calls = []

    def fake_run_single_scenario(name, config, report_dir, **kwargs):
        calls.append((name, report_dir.name, dict(config)))
        total_steps = config["chunk_steps"] * config["chunks"]
        if report_dir.name == "smoke":
            return make_result(name, steps=7, expected_steps=total_steps, passed=True)
        return make_result(name, steps=total_steps, expected_steps=total_steps, passed=True)

    monkeypatch.setattr(runner, "run_single_scenario", fake_run_single_scenario)

    args = SimpleNamespace(
        scenario="arrival_normal",
        mode="auto",
        max_chunks=3,
        smoke_steps=7,
        skip_smoke=False,
        execution_profile="deep_fast",
        llm_mode=None,
        embedding_mode=None,
        seed=1337,
    )

    exit_code, summary, _ = runner.run_regression_flow(args)

    assert exit_code == 0
    assert summary["smoke_passed"] is True
    assert summary["deep_started"] is True
    assert summary["deep_completed"] is True
    assert [call[1] for call in calls] == ["smoke", "deep"]
    assert calls[0][2]["chunks"] == 7
    assert calls[1][2]["chunks"] == 3


def test_deep_mode_respects_max_chunks_without_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "SCENARIO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "datetime", FixedDateTime)

    calls = []

    def fake_run_single_scenario(name, config, report_dir, **kwargs):
        calls.append((name, report_dir.name, dict(config)))
        total_steps = config["chunk_steps"] * config["chunks"]
        return make_result(name, steps=total_steps, expected_steps=total_steps, passed=True)

    monkeypatch.setattr(runner, "run_single_scenario", fake_run_single_scenario)

    args = SimpleNamespace(
        scenario="bottleneck",
        mode="deep",
        max_chunks=2,
        smoke_steps=7,
        skip_smoke=True,
        execution_profile="deep_fast",
        llm_mode=None,
        embedding_mode=None,
        seed=1337,
    )

    exit_code, summary, _ = runner.run_regression_flow(args)

    assert exit_code == 0
    assert summary["smoke_results"] == []
    assert summary["deep_started"] is True
    assert summary["deep_completed"] is True
    assert len(calls) == 1
    assert calls[0][0] == "bottleneck_imaging"
    assert calls[0][1] == "deep"
    assert calls[0][2]["chunks"] == 2


def test_launch_backend_defaults_to_local_llm_modes(tmp_path, monkeypatch):
    captured = {}

    class DummyProcess:
        def __init__(self):
            self.returncode = None

    def fake_popen(cmd, cwd, env, stdout, stderr):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        return DummyProcess()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)

    runtime_env = runner.resolve_runtime_env("deep_fast")
    proc, log_file = runner.launch_backend(
        "origin",
        "target",
        tmp_path / "runtime.log",
        tmp_path / "temp",
        runtime_env_overrides=runtime_env,
    )

    log_file.close()

    assert isinstance(proc, DummyProcess)
    assert captured["env"]["LLM_MODE"] == "local_only"
    assert captured["env"]["EMBEDDING_MODE"] == "local_only"
    assert captured["env"]["USE_LOCAL_EMBEDDINGS"] == "1"


def test_send_command_writes_atomic_json_file(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.time, "time", lambda: 1234.567)

    command_id = runner.send_command("run 1", tmp_path)
    commands_dir = tmp_path / "commands"
    command_path = commands_dir / f"cmd_{command_id}.json"

    assert command_id == "1234567"
    assert command_path.exists()
    assert not any(commands_dir.glob("*.tmp"))
    payload = runner.read_json(command_path, default={})
    assert payload["command"] == "run 1"
    assert payload["id"] == command_id


def test_run_analysis_requests_fresh_compression(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, cwd, capture_output, text, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    patient_csv = tmp_path / "patient_time_metrics.csv"
    ctas_csv = tmp_path / "ctas_daily_metrics.csv"
    resource_json = tmp_path / "resource_event_metrics.json"
    patient_csv.write_text("patient,ctas_level\n", encoding="utf-8")
    ctas_csv.write_text("date,ctas_level\n", encoding="utf-8")
    resource_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "ANALYSIS_ROOT", tmp_path)

    scenario_report_dir = tmp_path / "scenario"
    scenario_report_dir.mkdir(parents=True, exist_ok=True)

    runner.run_analysis("arrival_normal-seed_1337_repeat_1-run", scenario_report_dir)

    assert "--refresh-compressed" in captured["cmd"]
    assert captured["cmd"][0].endswith("python.exe")
    assert (scenario_report_dir / "analysis_run.json").exists()
    assert (scenario_report_dir / "patient_time_metrics.csv").exists()


def test_resolve_runtime_env_realism_check_defaults():
    env = runner.resolve_runtime_env("realism_check")

    assert env["LLM_MODE"] == "remote_only"
    assert env["EMBEDDING_MODE"] == "hybrid"
    assert env["USE_LOCAL_EMBEDDINGS"] == "0"


def test_classify_runtime_log_flags_treats_hybrid_recovery_as_non_fatal():
    flags = runner.classify_runtime_log_flags(
        "\n".join(
            [
                "Error: curl.exe failed: curl: (7) Failed to connect",
                "[runtime] llm safe legacy request hybrid fallback",
            ]
        )
    )

    assert flags["curl_error_seen"] is True
    assert flags["hybrid_fallback_recovered"] is True
    assert flags["curl_failed"] is False


def test_classify_runtime_log_flags_marks_unrecovered_curl_failure():
    flags = runner.classify_runtime_log_flags("Error: curl.exe failed: curl: (7) Failed to connect")

    assert flags["curl_error_seen"] is True
    assert flags["hybrid_fallback_recovered"] is False
    assert flags["curl_failed"] is True


def test_run_reproducibility_flow_aggregates_same_and_different_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "SCENARIO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "datetime", FixedDateTime)

    calls = []

    def fake_run_single_scenario(name, config, report_dir, **kwargs):
        calls.append((name, report_dir, dict(config), dict(kwargs)))
        seed = int(config["meta_updates"]["seed"])
        steps = config["chunk_steps"] * config["chunks"]
        result = make_result(name, steps=steps, expected_steps=steps, passed=True)
        result["meta_updates"] = {"seed": seed}
        result["sample_summary"] = {
            "max_current_patients": seed,
            "max_doctor_global_queue": seed + 1,
            "max_triage_queue": 2,
            "max_imaging_waiting": 0,
            "max_boarding_timeout_events": 0,
        }
        result["analysis_artifacts"] = {
            "patient_time_metrics_rows": [
                {
                    "patient": "Patient 1",
                    "ctas_level": "3",
                    "testing_kind": "lab",
                    "boarding_timeout_occurred": "False",
                    "wait_minutes": str(seed),
                    "treatment_minutes": str(seed + 1),
                    "total_ed_minutes": str(seed + 2),
                }
            ],
            "patient_metrics": {
                "patient_rows": seed,
                "patient_counts_by_ctas": {"3": seed},
            },
            "ctas_metrics": {
                "3": {
                    "patients": seed,
                    "avg_wait_minutes": float(seed),
                }
            },
            "resource_metrics": {
                "lab_patients": seed + 2,
            },
        }
        result["samples"] = [
            {
                "observed_step": steps,
                "status": {
                    "current_patients": seed,
                    "queues": {"doctor_global": seed + 1, "triage": 2, "imaging_waiting": 0},
                    "resources": {"boarding_timeout_events": 0},
                },
            }
        ]
        return result

    monkeypatch.setattr(runner, "run_single_scenario", fake_run_single_scenario)

    args = SimpleNamespace(
        scenario="arrival_normal",
        mode="deep",
        max_chunks=5,
        smoke_steps=7,
        skip_smoke=True,
        execution_profile="deep_fast",
        llm_mode=None,
        embedding_mode=None,
        seed=1337,
        reproducibility=True,
        repeats=2,
        compare_seeds=[2024],
    )

    exit_code, summary, run_dir = runner.run_reproducibility_flow(args)

    assert exit_code == 0
    assert summary["all_runs_passed"] is True
    assert len(summary["same_seed_results"]) == 2
    assert len(summary["different_seed_results"]) == 1
    scenario_summary = summary["scenario_summaries"][0]
    assert scenario_summary["same_seed"]["seed"] == 1337
    assert scenario_summary["same_seed"]["runs"] == 2
    assert scenario_summary["same_seed"]["metric_spread"]["max_current_patients"]["range"] == 0
    assert scenario_summary["same_seed"]["fine_grained_metric_spread"]["patient_metrics.patient_rows"]["range"] == 0
    pairwise = scenario_summary["same_seed"]["pairwise_patient_resource_trace_diffs"][0]["diff"]
    assert pairwise["patient_time_metrics"]["numeric_fields"]["wait_minutes"]["max_abs_diff"] == 0.0
    assert pairwise["sampled_status_trace"]["metrics"]["current_patients"]["max_abs_diff"] == 0
    assert scenario_summary["different_seed"][0]["seed"] == 2024
    assert scenario_summary["different_seed"][0]["diff_vs_same_seed_reference"]["max_current_patients"] == 687
    assert scenario_summary["different_seed"][0]["fine_grained_diff_vs_same_seed_reference"]["patient_metrics.patient_rows"] == 687
    assert scenario_summary["different_seed"][0]["patient_resource_trace_diff_vs_same_seed_reference"]["patient_time_metrics"]["numeric_fields"]["wait_minutes"]["max_abs_diff"] == 687.0
    assert (run_dir / "summary.json").exists()
    assert len(calls) == 3
