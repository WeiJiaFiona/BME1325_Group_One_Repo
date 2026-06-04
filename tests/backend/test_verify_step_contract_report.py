import json
import sys
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_step_contract import _export_dialogue_report, _check_week13_failure_metrics_schema


def test_export_dialogue_report_generates_markdown(tmp_path: Path):
    sim_dir = tmp_path / "curr_sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    trace_path = sim_dir / "dialogue_trace.jsonl"
    record = {
        "run_id": "demo-run",
        "step": 3,
        "persona": "Doctor 1",
        "participants": ["Doctor 1", "Patient 1"],
        "chat": [["Doctor 1", "hello"], ["Patient 1", "thanks"]],
        "source_type": "agent_chat_v2_iterative",
        "llm_mode": "hybrid",
        "generator": "agent_chat_v2",
        "prompt_template_path": "persona/prompt_template/ED/v3_ChatGPT/Doctor/iterative_convo_v1.txt",
        "summary_template_path": "persona/prompt_template/ED/v3_ChatGPT/Doctor/summarize_conversation_v1.txt",
        "fallback_used": False,
        "fallback_reason": None,
        "linked_movement_file": "movement/3.json",
    }
    trace_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    report_path = tmp_path / "artifacts" / "dialogue_provenance_report.md"
    count = _export_dialogue_report(sim_dir, report_path)

    assert count == 1
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Dialogue Provenance Report" in content
    assert "Doctor 1" in content
    assert "agent_chat_v2_iterative" in content


def test_week13_failure_metrics_missing_defaults_to_warning():
    status_payload = {"resources": {}, "system_health": {}}
    warnings, failures = _check_week13_failure_metrics_schema(status_payload, strict=False)
    assert warnings
    assert not failures
    assert "WARNING:" in warnings[0]


def test_week13_failure_metrics_strict_mode_hard_fails():
    status_payload = {"resources": {}, "system_health": {}}
    warnings, failures = _check_week13_failure_metrics_schema(status_payload, strict=True)
    assert not warnings
    assert failures


def test_week13_failure_metrics_present_passes():
    status_payload = {
        "resources": {
            "failure_rate": 0.1,
            "failed_patients_count": 1,
            "failure_reason_counts": {},
            "system_failed": False,
        },
        "system_health": {"failed": False},
    }
    warnings, failures = _check_week13_failure_metrics_schema(status_payload, strict=True)
    assert not warnings
    assert not failures
