from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app_core.clinical_kb.validators import DEFAULT_KB_ROOT


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    selective_rag: bool
    priority: int


def _load_intent_ontology(kb_root: Path) -> Dict[str, Any]:
    obj = yaml.safe_load((kb_root / "ontologies" / "intent_ontology.yaml").read_text(encoding="utf-8")) or {}
    return obj if isinstance(obj, dict) else {}


def classify_intent(text: str, *, kb_root: Path = DEFAULT_KB_ROOT) -> IntentMatch:
    payload = _load_intent_ontology(kb_root)
    intents = payload.get("intents", {}) if isinstance(payload.get("intents", {}), dict) else {}
    t = (text or "").strip()
    best = IntentMatch(intent="free_text_update", selective_rag=True, priority=0)
    for name, row in intents.items():
        if not isinstance(row, dict):
            continue
        pats = row.get("patterns", []) or []
        prio = int(row.get("priority", 0) or 0)
        sel = bool(row.get("selective_rag", False))
        for p in pats:
            try:
                if re.search(str(p), t, flags=re.IGNORECASE):
                    cand = IntentMatch(intent=str(name), selective_rag=sel, priority=prio)
                    if cand.priority > best.priority:
                        best = cand
                    break
            except re.error:
                continue
    return best


def should_query_doctor_kb(
    *,
    intent: IntentMatch,
    complaint_id: str,
    next_slot: str,
    kb_available: bool,
) -> bool:
    if not kb_available:
        return False
    if not complaint_id or not next_slot:
        return False
    if intent.intent in {"smalltalk", "confirm_yes_no"}:
        return False
    if intent.selective_rag:
        return True
    # Default allow when we have a next_slot and want better phrasing.
    return True

