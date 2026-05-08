from __future__ import annotations

from typing import Any, Dict

from app_core.app.llm_adapter import generate_from_prompt
from app_core.doctor_llm.prompts import prompt_answer_patient_test


def answer_patient_test_question(
    *,
    patient_text: str,
    language: str,
    complaint_id: str,
    next_slot: str,
    evidence: Dict[str, Any],
) -> str:
    fallback = ""
    for it in evidence.get("explanation_evidence", []) or []:
        t = str((it or {}).get("text", "")).strip()
        if t:
            fallback = t
            break
    if not fallback:
        fallback = "This depends on risk features. We can start with basic evaluation and then decide the best test."
    prompt = prompt_answer_patient_test(
        language=language,
        complaint_id=complaint_id,
        next_slot=next_slot,
        patient_text=patient_text,
        evidence=evidence,
    )
    return generate_from_prompt(prompt, fallback=fallback)
