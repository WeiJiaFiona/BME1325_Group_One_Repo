from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml

from app_core.clinical_kb.registry import DEFAULT_REGISTRY, registry_map


DEFAULT_KB_ROOT = Path(__file__).resolve().parents[2] / "RAG" / "doctor_kb"


@dataclass(frozen=True)
class ValidationIssue:
    level: str  # error | warn
    message: str
    path: str = ""


def _read_yaml(path: Path) -> Dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(obj, dict):
        return {}
    return obj


def _load_slot_ontology(kb_root: Path) -> Dict[str, Any]:
    return _read_yaml(kb_root / "ontologies" / "slot_ontology.yaml")


def _load_intent_ontology(kb_root: Path) -> Dict[str, Any]:
    return _read_yaml(kb_root / "ontologies" / "intent_ontology.yaml")


def _template_keys(kb_root: Path) -> Set[str]:
    t = _read_yaml(kb_root / "sources" / "_template.yaml")
    return set(t.keys())


def validate_all_sources(
    *,
    kb_root: Path = DEFAULT_KB_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    reg = registry_map(registry_path)
    template_keys = _template_keys(kb_root)

    slot_ont = _load_slot_ontology(kb_root)
    slot_defs = slot_ont.get("slots", {}) if isinstance(slot_ont.get("slots", {}), dict) else {}
    allowed_slots = set(slot_defs.keys())

    intent_ont = _load_intent_ontology(kb_root)
    intents = intent_ont.get("intents", {}) if isinstance(intent_ont.get("intents", {}), dict) else {}
    if not intents:
        issues.append(ValidationIssue("error", "intent_ontology.yaml has no intents"))

    complaint_ids = set()
    global_question_ids: Set[str] = set()
    global_link_ids: Set[str] = set()
    global_expl_ids: Set[str] = set()
    global_red_ids: Set[str] = set()

    for cid, item in reg.items():
        if cid in complaint_ids:
            issues.append(ValidationIssue("error", f"Duplicate complaint_id in registry: {cid}"))
        complaint_ids.add(cid)

        src_path = kb_root / item.source
        if not src_path.exists():
            issues.append(ValidationIssue("error", f"Missing source file: {src_path}", path=str(src_path)))
            continue

        src = _read_yaml(src_path)
        if not src:
            issues.append(ValidationIssue("error", f"Empty/invalid YAML: {src_path}", path=str(src_path)))
            continue

        # Template conformance: require at least all template keys.
        missing = [k for k in template_keys if k not in src]
        if missing:
            issues.append(ValidationIssue("error", f"Source missing keys {missing}", path=str(src_path)))

        if str(src.get("complaint_id", "")).strip() != cid:
            issues.append(ValidationIssue("error", f"complaint_id mismatch in {src_path}", path=str(src_path)))

        # Provenance required fields
        source_block = src.get("source", {})
        prov_keys = [
            "source_guideline",
            "source_section",
            "curator",
            "review_status",
            "effective_date",
            "evidence_level",
        ]
        if not isinstance(source_block, dict) or any(not str(source_block.get(k, "")).strip() for k in prov_keys):
            issues.append(ValidationIssue("error", "Missing required provenance fields", path=str(src_path)))

        # question_graph validation
        qg = src.get("question_graph", []) or []
        if not isinstance(qg, list) or not qg:
            issues.append(ValidationIssue("error", "question_graph must be non-empty list", path=str(src_path)))
        else:
            local_qids: Set[str] = set()
            local_lids: Set[str] = set()
            for q in qg:
                if not isinstance(q, dict):
                    issues.append(ValidationIssue("error", "question_graph item must be dict", path=str(src_path)))
                    continue
                qid = str(q.get("question_id", "")).strip()
                lid = str(q.get("link_id", "")).strip()
                slot = str(q.get("slot", "")).strip()
                if not qid or not lid or not slot:
                    issues.append(ValidationIssue("error", "question_graph item missing question_id/link_id/slot", path=str(src_path)))
                if qid in local_qids:
                    issues.append(ValidationIssue("error", f"Duplicate question_id in complaint: {qid}", path=str(src_path)))
                local_qids.add(qid)
                if lid in local_lids:
                    issues.append(ValidationIssue("error", f"Duplicate link_id in complaint: {lid}", path=str(src_path)))
                local_lids.add(lid)
                # Global uniqueness (simple)
                gqid = f"{cid}:{qid}"
                glid = f"{cid}:{lid}"
                if gqid in global_question_ids:
                    issues.append(ValidationIssue("error", f"Global duplicate question_id: {gqid}", path=str(src_path)))
                global_question_ids.add(gqid)
                if glid in global_link_ids:
                    issues.append(ValidationIssue("error", f"Global duplicate link_id: {glid}", path=str(src_path)))
                global_link_ids.add(glid)
                # Ontology compliance
                if slot and slot not in allowed_slots:
                    issues.append(ValidationIssue("error", f"Unknown slot `{slot}` (not in slot_ontology)", path=str(src_path)))
                # Text non-empty
                text = q.get("text", {})
                if not isinstance(text, dict) or not str(text.get("zh", "")).strip() or not str(text.get("en", "")).strip():
                    issues.append(ValidationIssue("error", "question text.zh/text.en must be non-empty", path=str(src_path)))

        # explanations validation
        expl = src.get("explanations", []) or []
        if not isinstance(expl, list) or not expl:
            issues.append(ValidationIssue("error", "explanations must be non-empty list", path=str(src_path)))
        else:
            local_eids: Set[str] = set()
            has_patient_facing = False
            has_nonempty_patient_text = False
            for e in expl:
                if not isinstance(e, dict):
                    issues.append(ValidationIssue("error", "explanations item must be dict", path=str(src_path)))
                    continue
                eid = str(e.get("explanation_id", "")).strip()
                if not eid:
                    issues.append(ValidationIssue("error", "explanations item missing explanation_id", path=str(src_path)))
                    continue
                if eid in local_eids:
                    issues.append(ValidationIssue("error", f"Duplicate explanation_id in complaint: {eid}", path=str(src_path)))
                local_eids.add(eid)
                geid = f"{cid}:{eid}"
                if geid in global_expl_ids:
                    issues.append(ValidationIssue("error", f"Global duplicate explanation_id: {geid}", path=str(src_path)))
                global_expl_ids.add(geid)
                if str(e.get("scope", "")).strip() == "patient_facing":
                    has_patient_facing = True
                    txt = e.get("text", {})
                    zh = str(txt.get("zh", "")).strip() if isinstance(txt, dict) else ""
                    en = str(txt.get("en", "")).strip() if isinstance(txt, dict) else ""
                    if len(zh) >= 40 or len(en) >= 40:
                        has_nonempty_patient_text = True
            if not has_patient_facing:
                issues.append(ValidationIssue("error", "Must include at least one patient_facing explanation", path=str(src_path)))
            if not has_nonempty_patient_text:
                issues.append(ValidationIssue("error", "Patient-facing explanation text too short/empty", path=str(src_path)))

        # red flags validation
        rf = src.get("red_flags", []) or []
        if not isinstance(rf, list) or not rf:
            issues.append(ValidationIssue("error", "red_flags must be non-empty list", path=str(src_path)))
        else:
            local_rids: Set[str] = set()
            for r in rf:
                if not isinstance(r, dict):
                    issues.append(ValidationIssue("error", "red_flags item must be dict", path=str(src_path)))
                    continue
                rid = str(r.get("red_flag_id", "")).strip()
                if not rid:
                    issues.append(ValidationIssue("error", "red_flags item missing red_flag_id", path=str(src_path)))
                    continue
                if rid in local_rids:
                    issues.append(ValidationIssue("error", f"Duplicate red_flag_id in complaint: {rid}", path=str(src_path)))
                local_rids.add(rid)
                grid = f"{cid}:{rid}"
                if grid in global_red_ids:
                    issues.append(ValidationIssue("error", f"Global duplicate red_flag_id: {grid}", path=str(src_path)))
                global_red_ids.add(grid)

        # required_slots check
        req = src.get("required_slots", []) or []
        if not isinstance(req, list) or not req:
            issues.append(ValidationIssue("error", "required_slots must be non-empty list", path=str(src_path)))
        else:
            for s in req:
                slot = str(s).strip()
                if slot and slot not in allowed_slots:
                    issues.append(ValidationIssue("error", f"required_slots includes unknown slot `{slot}`", path=str(src_path)))

        # light sanity for dates
        eff = str((source_block or {}).get("effective_date", "")).strip()
        if eff and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", eff):
            issues.append(ValidationIssue("warn", f"effective_date not ISO date: {eff}", path=str(src_path)))

    return issues


def validate_or_raise(*, kb_root: Path = DEFAULT_KB_ROOT, registry_path: Path = DEFAULT_REGISTRY) -> None:
    issues = validate_all_sources(kb_root=kb_root, registry_path=registry_path)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        msg = "; ".join([e.message for e in errors[:6]])
        raise ValueError(f"KB validation failed: {msg}")

