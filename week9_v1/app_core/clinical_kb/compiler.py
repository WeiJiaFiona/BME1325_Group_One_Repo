from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

from app_core.clinical_kb.registry import DEFAULT_REGISTRY, load_registry
from app_core.clinical_kb.validators import DEFAULT_KB_ROOT, validate_or_raise


def _read_yaml(path: Path) -> Dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return obj if isinstance(obj, dict) else {}


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _chunk_id(parts: Iterable[str]) -> str:
    raw = "|".join([_norm_text(p) for p in parts if p is not None])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_all(
    *,
    kb_root: Path = DEFAULT_KB_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> List[Path]:
    validate_or_raise(kb_root=kb_root, registry_path=registry_path)
    out_paths: List[Path] = []
    norm_dir = kb_root / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    for item in load_registry(registry_path):
        src_path = kb_root / item.source
        src = _read_yaml(src_path)
        payload = {
            "complaint_id": item.complaint_id,
            "title": src.get("title", ""),
            "aliases": src.get("aliases", []),
            "keywords": src.get("keywords", []),
            "related_symptoms": src.get("related_symptoms", []),
            "required_slots": src.get("required_slots", []),
            "question_graph": src.get("question_graph", []),
            "explanations": src.get("explanations", []),
            "red_flags": src.get("red_flags", []),
            "exam_focus": src.get("exam_focus", []),
            "test_considerations": src.get("test_considerations", []),
            "source": src.get("source", {}),
            "version": src.get("version", "v1"),
            "last_reviewed": src.get("last_reviewed", ""),
        }
        out_path = norm_dir / f"{item.complaint_id}.normalized.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        out_paths.append(out_path)
    return out_paths


def compile_chunks(
    *,
    kb_root: Path = DEFAULT_KB_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> Dict[str, Path]:
    validate_or_raise(kb_root=kb_root, registry_path=registry_path)
    compiled_dir = kb_root / "compiled"
    compiled_dir.mkdir(parents=True, exist_ok=True)
    question_f = compiled_dir / "question_chunks.jsonl"
    expl_f = compiled_dir / "explanation_chunks.jsonl"
    red_f = compiled_dir / "red_flag_chunks.jsonl"

    seen_ids: set[str] = set()

    def _emit(path: Path, row: Dict[str, Any]) -> None:
        cid = str(row.get("chunk_id", "")).strip()
        if cid in seen_ids:
            raise ValueError(f"Duplicate chunk_id: {cid}")
        seen_ids.add(cid)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # truncate old outputs
    for p in [question_f, expl_f, red_f]:
        if p.exists():
            p.unlink()

    norm_dir = kb_root / "normalized"
    if not norm_dir.exists():
        normalize_all(kb_root=kb_root, registry_path=registry_path)

    for item in load_registry(registry_path):
        norm_path = norm_dir / f"{item.complaint_id}.normalized.json"
        doc = json.loads(norm_path.read_text(encoding="utf-8"))
        prov = doc.get("source", {}) if isinstance(doc.get("source", {}), dict) else {}

        # questions
        for q in doc.get("question_graph", []) or []:
            slot = str(q.get("slot", "")).strip()
            text = q.get("text", {}) if isinstance(q.get("text", {}), dict) else {}
            zh = str(text.get("zh", "")).strip()
            en = str(text.get("en", "")).strip()
            chunk_text = zh or en
            cid = _chunk_id(["question", item.complaint_id, slot, str(q.get("question_id", "")), chunk_text])
            _emit(
                question_f,
                {
                    "chunk_id": cid,
                    "chunk_type": "question",
                    "complaint_id": item.complaint_id,
                    "slot": slot,
                    "question_id": str(q.get("question_id", "")).strip(),
                    "link_id": str(q.get("link_id", "")).strip(),
                    "text": chunk_text,
                    "text_zh": zh,
                    "text_en": en,
                    "purpose": str(q.get("purpose", "")).strip(),
                    "tags": list(q.get("tags", []) or []),
                    "provenance": prov,
                },
            )

        # explanations
        for e in doc.get("explanations", []) or []:
            topic = str(e.get("topic", "")).strip()
            txt = e.get("text", {}) if isinstance(e.get("text", {}), dict) else {}
            zh = str(txt.get("zh", "")).strip()
            en = str(txt.get("en", "")).strip()
            chunk_text = zh or en
            cid = _chunk_id(["explanation", item.complaint_id, topic, str(e.get("explanation_id", "")), chunk_text])
            _emit(
                expl_f,
                {
                    "chunk_id": cid,
                    "chunk_type": "explanation",
                    "complaint_id": item.complaint_id,
                    "topic": topic,
                    "explanation_id": str(e.get("explanation_id", "")).strip(),
                    "text": chunk_text,
                    "text_zh": zh,
                    "text_en": en,
                    "scope": str(e.get("scope", "")).strip(),
                    "related_tests": list(e.get("related_tests", []) or []),
                    "tags": list(e.get("tags", []) or []),
                    "provenance": prov,
                },
            )

        # red flags
        for r in doc.get("red_flags", []) or []:
            rid = str(r.get("red_flag_id", "")).strip()
            txt = r.get("text", {}) if isinstance(r.get("text", {}), dict) else {}
            rat = r.get("rationale", {}) if isinstance(r.get("rationale", {}), dict) else {}
            zh = str(txt.get("zh", "")).strip()
            en = str(txt.get("en", "")).strip()
            # For "why are you asking this?" patient questions, we want the retrievable
            # chunk to include both the red-flag statement and its rationale. This does
            # not affect hard-rule decisions; it only enriches patient-facing phrasing.
            chunk_text = zh or en
            rat_zh = str(rat.get("zh", "")).strip()
            rat_en = str(rat.get("en", "")).strip()
            if chunk_text and rat_zh and (zh or not en):
                chunk_text = f"{chunk_text} 为什么要问：{rat_zh}"
            elif chunk_text and rat_en:
                chunk_text = f"{chunk_text} Why we ask: {rat_en}"
            cid = _chunk_id(["red_flag", item.complaint_id, rid, chunk_text])
            _emit(
                red_f,
                {
                    "chunk_id": cid,
                    "chunk_type": "red_flag",
                    "complaint_id": item.complaint_id,
                    "red_flag_id": rid,
                    "text": chunk_text,
                    "text_zh": zh,
                    "text_en": en,
                    "rationale_zh": rat_zh,
                    "rationale_en": rat_en,
                    "tags": list(r.get("tags", []) or []),
                    "provenance": prov,
                },
            )

    return {"question": question_f, "explanation": expl_f, "red_flag": red_f}


def build_lex_indices(*, kb_root: Path = DEFAULT_KB_ROOT) -> List[Path]:
    compiled_dir = kb_root / "compiled"
    indices_dir = kb_root / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)

    def _tokenize(s: str) -> List[str]:
        s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", " ", (s or "").lower())
        toks = [t for t in s.split() if t]
        return toks

    def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
        return out

    outputs: List[Path] = []
    for kind, fname, key_fields in [
        ("question", "question_chunks.jsonl", ("complaint_id", "slot")),
        ("explanation", "explanation_chunks.jsonl", ("complaint_id", "topic")),
        ("red_flag", "red_flag_chunks.jsonl", ("complaint_id", "red_flag_id")),
    ]:
        src = compiled_dir / fname
        rows = _load_jsonl(src)
        postings: Dict[str, List[str]] = {}
        chunk_tokens: Dict[str, List[str]] = {}
        for r in rows:
            cid = str(r.get("chunk_id", "")).strip()
            key = "|".join([str(r.get(k, "")).strip() for k in key_fields])
            postings.setdefault(key, []).append(cid)
            chunk_tokens[cid] = _tokenize(str(r.get("text", "")))
        out_path = indices_dir / f"{kind}_lex.json"
        out_path.write_text(
            json.dumps({"kind": kind, "postings": postings, "chunk_tokens": chunk_tokens}, ensure_ascii=False),
            encoding="utf-8",
        )
        outputs.append(out_path)
    return outputs
