from __future__ import annotations

from typing import Any, Dict, List

from app_core.doctor_rag.retriever import RetrievalItem


def build_evidence_package(
    *,
    complaint_id: str,
    intent: str,
    next_slot: str,
    question_items: List[RetrievalItem],
    explanation_items: List[RetrievalItem],
    redflag_items: List[RetrievalItem],
) -> Dict[str, Any]:
    def _compact(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chunk_id": row.get("chunk_id"),
            "chunk_type": row.get("chunk_type"),
            "complaint_id": row.get("complaint_id"),
            "slot": row.get("slot", ""),
            "topic": row.get("topic", ""),
            "red_flag_id": row.get("red_flag_id", ""),
            "text": row.get("text", ""),
            "provenance": row.get("provenance", {}),
            "tags": row.get("tags", []),
        }

    return {
        "complaint_id": complaint_id,
        "intent": intent,
        "next_slot": next_slot,
        "question_evidence": [_compact(it.row) for it in question_items[:3]],
        "explanation_evidence": [_compact(it.row) for it in explanation_items[:3]],
        "redflag_evidence": [_compact(it.row) for it in redflag_items[:2]],
    }


def evidence_refs_from_items(items: List[RetrievalItem]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for it in items:
        row = it.row or {}
        refs.append(
            {
                "section": "doctor_kb",
                "chunk_type": row.get("chunk_type"),
                "chunk_id": row.get("chunk_id"),
                "complaint_id": row.get("complaint_id"),
                "slot": row.get("slot", ""),
                "topic": row.get("topic", ""),
                "red_flag_id": row.get("red_flag_id", ""),
                "score": it.score,
                "provenance": row.get("provenance", {}),
            }
        )
    return refs

