from __future__ import annotations

from typing import Any, Dict, List

from app_core.app.llm_adapter import generate_from_prompt
from app_core.doctor_llm.prompts import prompt_render_question


def render_question_from_slot(
    *,
    patient_text: str,
    language: str,
    complaint_id: str,
    next_slot: str,
    asked_question_ids: List[str],
    filled_slots: Dict[str, Any],
    evidence: Dict[str, Any],
) -> str:
    fallback = str((evidence.get("question_evidence", [{}])[0] or {}).get("text", "")).strip() or "When did it start?"
    prompt = prompt_render_question(
        language=language,
        complaint_id=complaint_id,
        next_slot=next_slot,
        patient_text=patient_text,
        asked_question_ids=asked_question_ids,
        filled_slots=filled_slots,
        evidence=evidence,
    )
    return generate_from_prompt(prompt, fallback=fallback)
