from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app_core.clinical_kb.loader import LoadedKB, load_kb
from app_core.clinical_kb.registry import registry_map
from app_core.doctor_rag.evidence_builder import build_evidence_package, evidence_refs_from_items
from app_core.doctor_rag.ranker import rerank
from app_core.doctor_rag.retriever import retrieve_explanations, retrieve_questions, retrieve_redflags
from app_core.doctor_rag.trigger import IntentMatch, classify_intent, should_query_doctor_kb
from app_core.doctor_llm.answer_tests import answer_patient_test_question
from app_core.doctor_llm.extract_fields import extract_fields_supplemental
from app_core.doctor_llm.render_question import render_question_from_slot


@dataclass(frozen=True)
class BridgeResult:
    rendered_question: str
    patient_explanation: str
    supplemental_extract: Dict[str, Any]
    evidence_refs: List[Dict[str, Any]]
    forbidden_content_detected: bool
    next_slot_echo: str
    disposition_proposed: Optional[str] = None
    urgency_proposed: Optional[str] = None


_FORBIDDEN_DISPOSITION = re.compile(r"\b(ICU|WARD|OUTPATIENT|transfer|admit|discharge)\b", flags=re.IGNORECASE)


def _is_forbidden(text: str) -> bool:
    if not text:
        return False
    return bool(_FORBIDDEN_DISPOSITION.search(text))


def run_bridge(
    *,
    complaint_id: str,
    patient_text: str,
    language: str,
    next_slot: str,
    filled_slots: Dict[str, Any],
    asked_question_ids: List[str],
) -> BridgeResult:
    # registry gate
    reg = registry_map()
    kb_available = complaint_id in reg

    intent = classify_intent(patient_text)
    do_rag = should_query_doctor_kb(intent=intent, complaint_id=complaint_id, next_slot=next_slot, kb_available=kb_available)
    if not do_rag:
        return BridgeResult(
            rendered_question="",
            patient_explanation="",
            supplemental_extract={},
            evidence_refs=[],
            forbidden_content_detected=False,
            next_slot_echo=next_slot,
        )

    kb: LoadedKB = load_kb()

    # retrieval by intent
    question_items = []
    explanation_items = []
    redflag_items = []

    if intent.intent in {"ask_imaging", "ask_labs", "ask_next_steps"}:
        # map intent to default explanation topics
        topic = {
            "ask_imaging": "ct_vs_mri",
            "ask_labs": "labs_common",
            "ask_next_steps": "next_steps",
        }.get(intent.intent, "next_steps")
        explanation_items = rerank(
            retrieve_explanations(kb, complaint_id=complaint_id, topic=topic, query_text=patient_text, k=5)
        )
    elif intent.intent == "ask_why_question":
        redflag_items = rerank(retrieve_redflags(kb, complaint_id=complaint_id, query_text=patient_text, k=3))
    else:
        question_items = rerank(
            retrieve_questions(kb, complaint_id=complaint_id, next_slot=next_slot, query_text=patient_text, k=5)
        )

    # Always retrieve question phrasing evidence for next_slot to improve follow-up.
    question_items = question_items or rerank(
        retrieve_questions(kb, complaint_id=complaint_id, next_slot=next_slot, query_text=patient_text, k=5)
    )

    evidence = build_evidence_package(
        complaint_id=complaint_id,
        intent=intent.intent,
        next_slot=next_slot,
        question_items=question_items,
        explanation_items=explanation_items,
        redflag_items=redflag_items,
    )
    refs: List[Dict[str, Any]] = []
    refs.extend(evidence_refs_from_items(question_items[:3]))
    refs.extend(evidence_refs_from_items(explanation_items[:3]))
    refs.extend(evidence_refs_from_items(redflag_items[:2]))

    explanation = ""
    if intent.intent in {"ask_imaging", "ask_labs", "ask_next_steps", "ask_why_question"}:
        explanation = answer_patient_test_question(
            patient_text=patient_text,
            language=language,
            complaint_id=complaint_id,
            next_slot=next_slot,
            evidence=evidence,
        )

    rendered_q = render_question_from_slot(
        patient_text=patient_text,
        language=language,
        complaint_id=complaint_id,
        next_slot=next_slot,
        asked_question_ids=asked_question_ids,
        filled_slots=filled_slots,
        evidence=evidence,
    )

    supplemental = extract_fields_supplemental(
        patient_text=patient_text,
        language=language,
        complaint_id=complaint_id,
        next_slot=next_slot,
        filled_slots=filled_slots,
    )

    forbidden = _is_forbidden(explanation) or _is_forbidden(rendered_q)
    if forbidden:
        explanation = ""
        rendered_q = ""
        supplemental = {}
        refs = []

    # contract invariants: never change next_slot, never propose disposition.
    return BridgeResult(
        rendered_question=rendered_q.strip(),
        patient_explanation=explanation.strip(),
        supplemental_extract=supplemental,
        evidence_refs=refs,
        forbidden_content_detected=forbidden,
        next_slot_echo=next_slot,
        disposition_proposed=None,
        urgency_proposed=None,
    )

