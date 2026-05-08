from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app_core.clinical_kb.loader import LoadedKB


@dataclass(frozen=True)
class RetrievalItem:
    chunk_id: str
    score: float
    row: Dict[str, Any]


def _tokenize(s: str) -> List[str]:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", " ", (s or "").lower())
    toks = [t for t in s.split() if t]
    return toks


def retrieve_questions(
    kb: LoadedKB,
    *,
    complaint_id: str,
    next_slot: str,
    query_text: str,
    k: int = 5,
) -> List[RetrievalItem]:
    idx = kb.indices.get("question", {})
    postings = idx.get("postings", {}) if isinstance(idx.get("postings", {}), dict) else {}
    chunk_tokens = idx.get("chunk_tokens", {}) if isinstance(idx.get("chunk_tokens", {}), dict) else {}
    key = f"{complaint_id}|{next_slot}"
    cand = postings.get(key, []) or []
    q_toks = set(_tokenize(query_text))
    scored: List[Tuple[float, str]] = []
    for cid in cand:
        toks = set(chunk_tokens.get(cid, []) or [])
        overlap = len(q_toks & toks)
        scored.append((float(overlap), cid))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[RetrievalItem] = []
    for s, cid in scored[:k]:
        row = kb.chunks.get(cid, {})
        out.append(RetrievalItem(chunk_id=cid, score=s, row=row))
    return out


def retrieve_explanations(
    kb: LoadedKB,
    *,
    complaint_id: str,
    topic: str,
    query_text: str,
    k: int = 5,
) -> List[RetrievalItem]:
    idx = kb.indices.get("explanation", {})
    postings = idx.get("postings", {}) if isinstance(idx.get("postings", {}), dict) else {}
    chunk_tokens = idx.get("chunk_tokens", {}) if isinstance(idx.get("chunk_tokens", {}), dict) else {}
    key = f"{complaint_id}|{topic}"
    cand = postings.get(key, []) or []
    if not cand:
        # fallback: any topic under complaint
        prefix = f"{complaint_id}|"
        for k2, ids in postings.items():
            if str(k2).startswith(prefix):
                cand.extend(list(ids or []))
    q_toks = set(_tokenize(query_text))
    scored: List[Tuple[float, str]] = []
    for cid in cand:
        toks = set(chunk_tokens.get(cid, []) or [])
        overlap = len(q_toks & toks)
        scored.append((float(overlap), cid))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[RetrievalItem] = []
    for s, cid in scored[:k]:
        row = kb.chunks.get(cid, {})
        out.append(RetrievalItem(chunk_id=cid, score=s, row=row))
    return out


def retrieve_redflags(
    kb: LoadedKB,
    *,
    complaint_id: str,
    query_text: str,
    k: int = 3,
) -> List[RetrievalItem]:
    idx = kb.indices.get("red_flag", {})
    postings = idx.get("postings", {}) if isinstance(idx.get("postings", {}), dict) else {}
    chunk_tokens = idx.get("chunk_tokens", {}) if isinstance(idx.get("chunk_tokens", {}), dict) else {}
    prefix = f"{complaint_id}|"
    cand: List[str] = []
    for key, ids in postings.items():
        if str(key).startswith(prefix):
            cand.extend(list(ids or []))
    q_toks = set(_tokenize(query_text))
    scored: List[Tuple[float, str]] = []
    for cid in cand:
        toks = set(chunk_tokens.get(cid, []) or [])
        overlap = len(q_toks & toks)
        scored.append((float(overlap), cid))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[RetrievalItem] = []
    for s, cid in scored[:k]:
        row = kb.chunks.get(cid, {})
        out.append(RetrievalItem(chunk_id=cid, score=s, row=row))
    return out

