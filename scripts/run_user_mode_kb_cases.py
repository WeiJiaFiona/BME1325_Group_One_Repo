from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CASES_DIR = Path("test_his_results/user/cases")
RESULTS_DIR = Path("test_his_results/user/results")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _pick_answer(question: str, expected: List[Dict[str, Any]], *, default: str) -> str:
    q = _normalize_text(question).lower()
    # Lightweight heuristics so the patient is never forced into a rigid template.
    triggers: List[Tuple[str, List[str]]] = [
        ("onset_time", ["什么时候", "何时", "when", "开始", "几点", "哪一天"]),
        ("duration", ["多久", "持续", "几天", "how long"]),
        ("location", ["哪里", "部位", "位置", "在哪"]),
        ("worsening", ["加重", "更严重", "worse"]),
        ("fever", ["发热", "发烧", "fever"]),
        ("syncope", ["晕厥", "晕倒", "昏倒", "faint", "syncope"]),
        ("chest_pain_sob", ["胸痛", "胸闷", "气短", "呼吸困难", "short of breath"]),
        ("pregnancy", ["怀孕", "月经", "pregnant", "period"]),
        ("vomiting", ["呕吐", "吐", "vomit"]),
        ("gi_bleeding", ["黑便", "便血", "blood", "tarry"]),
        ("neuro_deficits", ["麻", "无力", "说话", "偏", "视物", "神经"]),
        ("bowel_bladder", ["尿", "大便", "失禁", "retention"]),
        ("trauma", ["外伤", "摔", "撞", "trauma", "injury"]),
    ]
    hinted_slot: Optional[str] = None
    for slot, words in triggers:
        if any(w in q for w in words):
            hinted_slot = slot
            break

    if hinted_slot:
        for item in expected:
            slot = str(item.get("slot", "")).strip()
            if slot == hinted_slot and str(item.get("patient_answer", "")).strip():
                return str(item["patient_answer"]).strip()

    # Otherwise answer the first still-unused expected slot answer.
    for item in expected:
        if item.get("_used"):
            continue
        ans = str(item.get("patient_answer", "")).strip()
        if ans:
            item["_used"] = True
            return ans

    return default


def _ensure_llm_and_rag_ready() -> Dict[str, Any]:
    from app_core.app.llm_adapter import llm_enabled  # lazy import
    from app_core.clinical_kb.registry import registry_map

    kb = registry_map()
    complaints = sorted(list(kb.keys()))
    return {
        "llm_enabled": bool(llm_enabled()),
        "rag_registry_count": len(complaints),
        "rag_registry_keys": complaints,
        "env_ENABLE_LLM_AGENTS": os.getenv("ENABLE_LLM_AGENTS", ""),
        "env_EDSIM_MODEL": os.getenv("EDSIM_MODEL", ""),
        "env_EDSIM_MODEL_ENDPOINT": os.getenv("EDSIM_MODEL_ENDPOINT", ""),
    }


def _run_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    import app_core.app.api_v1 as api_v1

    api_v1.reset_user_mode_session()
    expected = list(payload.get("expected_questions", []) or [])

    transcript: List[Dict[str, str]] = []

    def _append(role: str, content: str) -> None:
        transcript.append({"role": str(role), "text": str(content)})

    # Send the initial complaint message; this triggers triage/calling and then doctor.
    user_msg = str(payload.get("initial_patient_message", "")).strip()
    _append("PATIENT", user_msg)
    resp = api_v1.user_mode_chat_turn(user_msg)
    for msg in resp.get("messages", []) or []:
        agent = msg.get("agent") or msg.get("role") or ""
        text = msg.get("text") or msg.get("content") or ""
        _append(str(agent), str(text))

    turns = 0
    max_turns = 12
    while turns < max_turns:
        turns += 1
        tail = resp.get("transcript_tail", []) or []
        last_doctor = ""
        for item in reversed(tail):
            if str(item.get("role", "")).strip().lower() == "doctor":
                last_doctor = str(item.get("text", "") or item.get("content", "")).strip()
                break

        session = resp.get("session", {}) or {}
        phase = str(session.get("phase", "")).strip()
        if phase in {"DONE"}:
            break
        if not last_doctor:
            break

        answer = _pick_answer(
            last_doctor,
            expected,
            default="好的。我可以再补充：症状在持续，没有明显外伤史，也没有其他特别情况。",
        )
        _append("PATIENT", answer)
        resp = api_v1.user_mode_chat_turn(answer)
        for msg in resp.get("messages", []) or []:
            agent = msg.get("agent") or msg.get("role") or ""
            text = msg.get("text") or msg.get("content") or ""
            _append(str(agent), str(text))

        # Stop once doctor disposition happened (bed nurse / transfer).
        for msg in resp.get("messages", []) or []:
            if str(msg.get("event_type", "")).startswith("doctor_disposition"):
                turns = max_turns
                break

    # Capture RAG retrieval traces when available.
    # The API response session payload is intentionally small; use the in-process
    # backing session object to introspect RAG/assessment traces.
    backing = getattr(api_v1, "_USER_MODE_SESSION", None) or {}
    shared = (backing.get("shared_memory") or {}) if isinstance(backing.get("shared_memory"), dict) else {}
    assess = shared.get("doctor_assessment") if isinstance(shared.get("doctor_assessment"), dict) else {}
    active_pids = assess.get("active_protocol_ids") if isinstance(assess.get("active_protocol_ids"), list) else []
    trace = assess.get("planner_trace") if isinstance(assess.get("planner_trace"), list) else []
    last = trace[-1] if trace else {}
    retrieval_result = last if isinstance(last, dict) else {}
    primary_pid = ""
    if active_pids and isinstance(active_pids[0], str):
        primary_pid = active_pids[0]
    if not primary_pid:
        primary_pid = str(retrieval_result.get("primary_protocol_id", "") or "")

    return {
        "case_id": payload.get("case_id"),
        "complaint_family": payload.get("complaint_family"),
        "ran_at": _utc_now_iso(),
        "llm_rag_runtime": _ensure_llm_and_rag_ready(),
        "final_phase": str((backing.get("phase") or "")),
        "encounter_id": str((backing.get("encounter_id") or "")),
        "rag_primary_protocol_id": str(primary_pid),
        "rag_assessment_snapshot": {
            "active_protocol_ids": active_pids,
            "normalized_complaints": assess.get("normalized_complaints", []),
            "missing_critical_slots": assess.get("missing_critical_slots", []),
            "filled_slots": assess.get("filled_slots", {}),
            "planner_trace_tail": trace[-3:],
        },
        "transcript": transcript,
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cases = sorted(CASES_DIR.glob("*.json"))
    if not cases:
        raise SystemExit(f"No cases found under {CASES_DIR}")

    runtime = _ensure_llm_and_rag_ready()
    if not runtime.get("llm_enabled"):
        raise SystemExit(
            "LLM is not enabled. Export env vars (EDSIM_MODEL_KEY/EDSIM_MODEL_ENDPOINT/EDSIM_MODEL) "
            "and ensure ENABLE_LLM_AGENTS=1 before running."
        )
    if runtime.get("rag_registry_count", 0) < 1:
        raise SystemExit("RAG registry is empty; doctor_kb may be missing or not compiled.")

    summary: Dict[str, Any] = {
        "ran_at": _utc_now_iso(),
        "runtime": runtime,
        "cases": [],
    }
    for path in cases:
        payload = _load_json(path)
        result = _run_case(payload)
        out_path = RESULTS_DIR / f"{payload.get('case_id','case')}.result.json"
        _write_json(out_path, result)
        summary["cases"].append(
            {
                "case_id": payload.get("case_id"),
                "complaint_family": payload.get("complaint_family"),
                "rag_primary_protocol_id": result.get("rag_primary_protocol_id"),
                "final_phase": result.get("final_phase"),
                "result_path": str(out_path),
            }
        )

    _write_json(RESULTS_DIR / "_summary.json", summary)


if __name__ == "__main__":
    main()
