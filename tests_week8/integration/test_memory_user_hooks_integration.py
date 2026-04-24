import pytest


def test_user_mode_emits_events_and_replay_export(tmp_path, monkeypatch):
    from app_core.app import api_v1
    from app_core.memory.service import create_memory_service

    monkeypatch.setenv("MEMORY_V1_ENABLED", "1")
    monkeypatch.setenv("MEMORY_V1_ROOT", str(tmp_path / "runtime_data" / "memory_user"))
    api_v1.reset_user_mode_session()

    # Start intake and progress to doctor disposition quickly (high acuity).
    api_v1.user_mode_chat_turn("你好")
    api_v1.user_mode_chat_turn("我胸口很闷，10级，出冷汗，喘不上气。")

    # Drive a few turns until done.
    for _ in range(12):
        status = api_v1.user_mode_session_status()
        if status["session"]["phase"] in {"DONE", "BED_NURSE_FLOW"}:
            break
        api_v1.user_mode_chat_turn("是的")
    status = api_v1.user_mode_session_status()

    ctx = api_v1._debug_user_memory_context()
    run_id = ctx["run_id"]
    mem_enc = ctx["memory_encounter_id"]

    service = create_memory_service(root=tmp_path / "runtime_data" / "memory_user", enabled=True)
    replay = service.export_replay(run_id=run_id, mode="user", encounter_id=mem_enc)

    event_types = [e["event_type"] for e in replay["events"]]
    assert "encounter_started" in event_types
    assert "vitals_measured" in event_types
    assert "triage_completed" in event_types
    assert "doctor_assessment_checkpoint" in event_types
    assert "disposition_decided" in event_types
    assert "handoff_requested" in event_types

    steps = [e["step"] for e in replay["events"]]
    assert steps == sorted(steps)

    # Summary should exist once we emitted checkpoints.
    assert replay["summaries"] != []
    # Chief complaint + doctor note should be visible in current summary payload (latest_doctor_findings).
    summary = replay["summaries"][-1]
    findings = summary.get("latest_doctor_findings", {})
    assert isinstance(findings, dict)
    assert isinstance(findings.get("chief_complaint", ""), str)
    assert findings.get("chief_complaint", "").strip() != ""
    # We don't require a final diagnosis, but we should have at least one patient-facing note/question recorded.
    assert isinstance(findings.get("latest_note", ""), str)
    assert findings.get("latest_note", "").strip() != ""


def test_user_mode_memory_ablation_off_creates_no_events(tmp_path, monkeypatch):
    from app_core.app import api_v1
    from app_core.memory.service import create_memory_service

    monkeypatch.setenv("MEMORY_V1_ENABLED", "0")
    monkeypatch.setenv("MEMORY_V1_ROOT", str(tmp_path / "runtime_data" / "memory_user"))
    api_v1.reset_user_mode_session()

    api_v1.user_mode_chat_turn("hello")
    api_v1.user_mode_chat_turn("abdominal pain 8/10")
    for _ in range(6):
        api_v1.user_mode_session_status()
        api_v1.user_mode_chat_turn("no fever")

    ctx = api_v1._debug_user_memory_context()
    service = create_memory_service(root=tmp_path / "runtime_data" / "memory_user", enabled=False)
    replay = service.export_replay(run_id=ctx["run_id"], mode="user", encounter_id=ctx["memory_encounter_id"])
    assert replay["events"] == []


def test_user_mode_fail_open_when_memory_raises(tmp_path, monkeypatch):
    from app_core.app import api_v1

    class ExplodingMemory:
        enabled = True

        def append_event(self, *_a, **_k):
            raise RuntimeError("boom append_event")

        def update_current_summary(self, *_a, **_k):
            raise RuntimeError("boom update_current_summary")

        def write_handoff_snapshot(self, *_a, **_k):
            raise RuntimeError("boom write_handoff_snapshot")

        def retrieve(self, *_a, **_k):
            raise RuntimeError("boom retrieve")

        def export_replay(self, *_a, **_k):
            raise RuntimeError("boom export")

        def append_audit(self, *_a, **_k):
            raise RuntimeError("boom audit")

    # Ensure memory is enabled so integration paths are exercised, but service explodes.
    monkeypatch.setenv("MEMORY_V1_ENABLED", "1")
    monkeypatch.setenv("MEMORY_V1_ROOT", str(tmp_path / "runtime_data" / "memory_user"))
    api_v1.reset_user_mode_session()
    monkeypatch.setattr(api_v1, "get_memory_service", lambda: ExplodingMemory())

    # Flow must still complete (or at least reach disposition/handoff) without raising.
    api_v1.user_mode_chat_turn("你好")
    api_v1.user_mode_chat_turn("我头很疼，9级，刚刚突然开始的，还恶心想吐。")
    for _ in range(12):
        st = api_v1.user_mode_session_status()["session"]["phase"]
        if st in {"BED_NURSE_FLOW", "DONE"}:
            break
        api_v1.user_mode_chat_turn("是的")
    assert api_v1.user_mode_session_status()["session"]["phase"] in {"BED_NURSE_FLOW", "DONE", "DOCTOR_CALLED"}
