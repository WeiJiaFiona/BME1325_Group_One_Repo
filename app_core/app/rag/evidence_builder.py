from __future__ import annotations

from typing import Any, Dict


def build_evidence_package(session: Dict[str, Any], retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
    shared = session.get("shared_memory", {})
    doctor_assessment = shared.get("doctor_assessment", {})
    return {
        "primary_protocol_id": retrieval_result.get("primary_protocol_id"),
        "secondary_protocol_ids": retrieval_result.get("secondary_protocol_ids", []),
        "retrieval_score": retrieval_result.get("retrieval_score", 0.0),
        "evidence_refs": retrieval_result.get("evidence_refs", []),
        "case_refs": retrieval_result.get("case_result", {}).get("case_refs", []),
        "case_protocol_scores": retrieval_result.get("case_result", {}).get("case_protocol_scores", {}),
        "normalized_complaints": retrieval_result.get("normalized_complaints", []),
        "doctor_data": doctor_assessment.get("doctor_data", {}),
        "vitals": shared.get("vitals", {}),
        "triage": shared.get("triage", {}),
    }
