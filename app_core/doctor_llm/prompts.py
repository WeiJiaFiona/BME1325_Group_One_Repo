from __future__ import annotations

from typing import Any, Dict, List


def _evidence_snippets(evidence: Dict[str, Any]) -> str:
    parts: List[str] = []
    for arr_key in ["question_evidence", "explanation_evidence", "redflag_evidence"]:
        for it in evidence.get(arr_key, []) or []:
            text = str((it or {}).get("text", "")).strip()
            if text:
                parts.append(text)
    return "\n".join(parts[:6]).strip()


def prompt_render_question(
    *,
    language: str,
    complaint_id: str,
    next_slot: str,
    patient_text: str,
    asked_question_ids: List[str],
    filled_slots: Dict[str, Any],
    evidence: Dict[str, Any],
) -> str:
    ev = _evidence_snippets(evidence)
    return (
        "You are an ED doctor.\n"
        f"Language={language}\n"
        f"Complaint={complaint_id}\n"
        f"next_slot={next_slot}\n"
        f"asked_question_ids={asked_question_ids}\n"
        f"filled_slots={filled_slots}\n"
        f"Patient={patient_text}\n"
        "Constraints:\n"
        "- Ask exactly ONE follow-up question.\n"
        "- Do NOT mention ICU/WARD/OUTPATIENT/transfer/admit/discharge.\n"
        "- Do NOT change the topic away from next_slot.\n"
        "- Prefer complaint-specific phrasing.\n"
        "Evidence snippets:\n"
        f"{ev}\n"
        "Return only the single question sentence."
    )


def prompt_answer_patient_test(
    *,
    language: str,
    complaint_id: str,
    next_slot: str,
    patient_text: str,
    evidence: Dict[str, Any],
) -> str:
    ev = _evidence_snippets(evidence)
    return (
        "You are an ED doctor.\n"
        f"Language={language}\n"
        f"Complaint={complaint_id}\n"
        f"next_slot={next_slot}\n"
        f"Patient={patient_text}\n"
        "Task: Patient asked about tests/imaging/why ask/next steps.\n"
        "Constraints:\n"
        "- Provide a concise patient-facing explanation.\n"
        "- Do NOT mention ICU/WARD/OUTPATIENT/transfer/admit/discharge.\n"
        "- Do NOT give a final diagnosis.\n"
        "- After answering, add one short line that naturally returns to the next_slot question.\n"
        "Evidence snippets:\n"
        f"{ev}\n"
        "Return 2-3 short sentences max."
    )

