from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_core.clinical_kb.validators import DEFAULT_KB_ROOT
from app_core.clinical_kb.compiler import build_lex_indices, compile_chunks, normalize_all


@dataclass
class LoadedKB:
    kb_root: Path
    chunks: Dict[str, Dict[str, Any]]  # chunk_id -> chunk row
    indices: Dict[str, Dict[str, Any]]  # kind -> index payload


def _load_jsonl(path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t:
            continue
        row = json.loads(t)
        cid = str(row.get("chunk_id", "")).strip()
        if cid:
            out[cid] = row
    return out


def load_compiled_chunks(kb_root: Path) -> Dict[str, Dict[str, Any]]:
    compiled = kb_root / "compiled"
    out: Dict[str, Dict[str, Any]] = {}
    for fname in ["question_chunks.jsonl", "explanation_chunks.jsonl", "red_flag_chunks.jsonl"]:
        p = compiled / fname
        if p.exists():
            out.update(_load_jsonl(p))
    return out


def load_lex_index(kb_root: Path, kind: str) -> Optional[Dict[str, Any]]:
    p = kb_root / "indices" / f"{kind}_lex.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_kb(*, kb_root: Path = DEFAULT_KB_ROOT) -> LoadedKB:
    # Ensure build artifacts exist (artifact-driven, local).
    compiled_dir = kb_root / "compiled"
    indices_dir = kb_root / "indices"
    if not compiled_dir.exists():
        normalize_all(kb_root=kb_root)
        compile_chunks(kb_root=kb_root)
    if not indices_dir.exists() or not any(indices_dir.glob("*_lex.json")):
        normalize_all(kb_root=kb_root)
        compile_chunks(kb_root=kb_root)
        build_lex_indices(kb_root=kb_root)
    chunks = load_compiled_chunks(kb_root)
    indices: Dict[str, Dict[str, Any]] = {}
    for kind in ["question", "explanation", "red_flag"]:
        idx = load_lex_index(kb_root, kind)
        if idx:
            indices[kind] = idx
    return LoadedKB(kb_root=kb_root, chunks=chunks, indices=indices)
