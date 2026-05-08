from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml


DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "RAG" / "doctor_kb" / "manifests" / "complaint_registry.yaml"


@dataclass(frozen=True)
class ComplaintRegistryItem:
    complaint_id: str
    source: str


def load_registry(path: Path = DEFAULT_REGISTRY) -> List[ComplaintRegistryItem]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    complaints = payload.get("complaints", []) or []
    out: List[ComplaintRegistryItem] = []
    for row in complaints:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("complaint_id", "")).strip()
        src = str(row.get("source", "")).strip()
        if cid and src:
            out.append(ComplaintRegistryItem(complaint_id=cid, source=src))
    return out


def registry_map(path: Path = DEFAULT_REGISTRY) -> Dict[str, ComplaintRegistryItem]:
    items = load_registry(path)
    return {it.complaint_id: it for it in items}

