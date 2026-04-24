from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Provenance:
    source_guideline: str
    source_section: str
    curator: str
    review_status: str
    effective_date: str
    evidence_level: str


@dataclass(frozen=True)
class KBQuestion:
    complaint_id: str
    slot: str
    question_id: str
    link_id: str
    text_zh: str
    text_en: str
    qtype: str
    required: bool
    purpose: str
    tags: List[str]
    provenance: Provenance


@dataclass(frozen=True)
class KBExplanation:
    complaint_id: str
    topic: str
    explanation_id: str
    text_zh: str
    text_en: str
    scope: str
    related_tests: List[str]
    tags: List[str]
    provenance: Provenance


@dataclass(frozen=True)
class KBRedFlag:
    complaint_id: str
    red_flag_id: str
    text_zh: str
    text_en: str
    rationale_zh: str
    rationale_en: str
    tags: List[str]
    provenance: Provenance


@dataclass(frozen=True)
class CompiledChunk:
    chunk_id: str
    chunk_type: str  # question | explanation | red_flag
    complaint_id: str
    slot: str  # slot for question, else ""
    topic: str  # topic for explanation, else ""
    red_flag_id: str  # for red_flag, else ""
    text: str
    meta: Dict[str, Any]


def as_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    raise TypeError(f"Unsupported object for as_dict: {type(obj)}")

