from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


CASE_BANK_FILE = Path(__file__).resolve().parents[1] / "case_bank" / "cases_v1.jsonl"


@dataclass
class CaseDoc:
    case_id: str
    protocol_id: str
    keywords: List[str]
    risk_flags: List[str]


_CASE_CACHE: List[CaseDoc] = []


def _load_cases() -> List[CaseDoc]:
    global _CASE_CACHE
    if _CASE_CACHE:
        return _CASE_CACHE
    out: List[CaseDoc] = []
    if not CASE_BANK_FILE.exists():
        _CASE_CACHE = out
        return out
    for line in CASE_BANK_FILE.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except Exception:
            continue
        out.append(
            CaseDoc(
                case_id=str(row.get("case_id", "")).strip(),
                protocol_id=str(row.get("protocol_id", "")).strip(),
                keywords=[str(x).lower() for x in row.get("keywords", [])],
                risk_flags=[str(x) for x in row.get("risk_flags", [])],
            )
        )
    _CASE_CACHE = out
    return out


def _score_case(case: CaseDoc, merged_text: str) -> Tuple[float, List[str]]:
    score = 0.0
    matched: List[str] = []
    for kw in case.keywords:
        if kw and kw in merged_text:
            score += 1.0
            matched.append(kw)
    return score, matched


def retrieve_cases(*, chief_complaint: str, symptoms: List[str], patient_message: str, top_k: int = 3) -> Dict[str, Any]:
    merged = " ".join([chief_complaint, " ".join(symptoms), patient_message]).lower().strip()
    ranked: List[Tuple[float, CaseDoc, List[str]]] = []
    for case in _load_cases():
        s, m = _score_case(case, merged)
        if s > 0:
            ranked.append((s, case, m))
    ranked.sort(key=lambda x: x[0], reverse=True)

    top = ranked[:top_k]
    protocol_scores: Dict[str, float] = {}
    risk_union: List[str] = []
    refs: List[Dict[str, Any]] = []

    for s, c, m in top:
        protocol_scores[c.protocol_id] = protocol_scores.get(c.protocol_id, 0.0) + s
        for rf in c.risk_flags:
            if rf not in risk_union:
                risk_union.append(rf)
        refs.append(
            {
                "case_id": c.case_id,
                "protocol_id": c.protocol_id,
                "section": "case_bank",
                "score": round(s, 3),
                "matched": m[:6],
            }
        )

    sorted_protocols = sorted(protocol_scores.items(), key=lambda x: x[1], reverse=True)
    top_protocols = [p for p, _ in sorted_protocols]

    return {
        "case_refs": refs,
        "case_protocol_scores": protocol_scores,
        "top_case_protocols": top_protocols,
        "risk_flags": risk_union,
        "fallback_used": len(refs) == 0,
    }
