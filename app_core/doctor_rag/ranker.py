from __future__ import annotations

from typing import List

from app_core.doctor_rag.retriever import RetrievalItem


def rerank(items: List[RetrievalItem]) -> List[RetrievalItem]:
    # Current lexical retriever already sorts by overlap; keep stable here.
    return list(items)

