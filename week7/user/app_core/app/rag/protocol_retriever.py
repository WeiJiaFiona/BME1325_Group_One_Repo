from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from app_core.app.rag.case_retriever import retrieve_cases


PROTOCOL_ROOT = Path(__file__).resolve().parents[1] / "protocols"


@dataclass
class ProtocolDoc:
    protocol_id: str
    version: str
    aliases: List[str]
    trigger_keywords: List[str]
    red_flags: List[str]
    required_slots: List[str]
    questions: List[Dict[str, Any]]
    urgency_rules: List[Dict[str, Any]]


_CACHE: List[ProtocolDoc] = []


def _load_docs() -> List[ProtocolDoc]:
    global _CACHE
    if _CACHE:
        return _CACHE
    docs: List[ProtocolDoc] = []
    for folder in sorted(PROTOCOL_ROOT.glob("*/v1.yaml")):
        payload = yaml.safe_load(folder.read_text(encoding="utf-8")) or {}
        docs.append(
            ProtocolDoc(
                protocol_id=str(payload.get("protocol_id", "")).strip(),
                version=str(payload.get("version", "v1")).strip() or "v1",
                aliases=[str(x).lower() for x in payload.get("chief_complaint_aliases", [])],
                trigger_keywords=[str(x).lower() for x in payload.get("trigger_keywords", [])],
                red_flags=[str(x) for x in payload.get("red_flags", [])],
                required_slots=[str(x) for x in payload.get("required_slots", [])],
                questions=list(payload.get("questions", [])),
                urgency_rules=list(payload.get("urgency_rules", [])),
            )
        )
    _CACHE = docs
    return _CACHE


def normalize_complaints(texts: List[str]) -> List[str]:
    merged = " ".join([t.lower() for t in texts if t]).strip()
    out: List[str] = []
    mapping = {
        "chest_pain": ["chest pain", "chest tight", "chest pressure", "胸痛", "胸闷", "胸口"],
        "dyspnea": ["shortness of breath", "dyspnea", "can't breathe", "呼吸困难", "喘不上"],
        "stroke": ["stroke", "face droop", "slurred", "单侧", "口角歪", "中风"],
        "sepsis": ["sepsis", "fever and chills", "高热", "寒战", "发冷发抖", "感染"],
        "trauma": ["trauma", "injury", "fracture", "fall", "骨折", "外伤", "摔"],
        "labor": ["labor", "delivery", "giving birth", "pregnant", "宫缩", "分娩", "生小孩", "破水", "羊水"],
        "abdominal_pain": ["abdominal pain", "belly pain", "epigastric pain", "腹痛", "肚子痛", "右下腹痛"],
        "anaphylaxis": ["anaphylaxis", "allergic reaction", "hives", "throat tight", "过敏反应", "喉咙紧", "荨麻疹"],
        "headache": ["headache", "severe headache", "worst headache", "头痛", "头很疼", "剧烈头痛", "偏头痛"],
    }
    for pid, hints in mapping.items():
        if any(h in merged for h in hints):
            out.append(pid)
    return out


def _score_doc(doc: ProtocolDoc, merged_text: str, normalized: List[str], vitals: Dict[str, Any]) -> Tuple[float, List[str]]:
    score = 0.0
    matched: List[str] = []

    if doc.protocol_id in normalized:
        score += 2.0
        matched.append(f"normalized:{doc.protocol_id}")

    for item in doc.aliases:
        if item and item in merged_text:
            score += 1.3
            matched.append(item)

    for item in doc.trigger_keywords:
        if item and item in merged_text:
            score += 0.8
            matched.append(item)

    spo2 = float(vitals.get("spo2", 97) or 97)
    sbp = float(vitals.get("sbp", 120) or 120)
    if spo2 < 90 and "hypoxia" in doc.red_flags:
        score += 1.2
        matched.append("vital:hypoxia")
    if sbp < 90 and "hypotension" in doc.red_flags:
        score += 1.2
        matched.append("vital:hypotension")

    return score, matched


def retrieve_protocols(
    *,
    chief_complaint: str,
    symptoms: List[str],
    patient_message: str,
    vitals: Dict[str, Any],
    top_k: int = 2,
) -> Dict[str, Any]:
    docs = _load_docs()
    texts = [chief_complaint, " ".join(symptoms), patient_message]
    merged = " ".join([t.lower() for t in texts if t]).strip()
    normalized = normalize_complaints(texts)
    case_result = retrieve_cases(
        chief_complaint=chief_complaint,
        symptoms=symptoms,
        patient_message=patient_message,
    )

    ranked: List[Tuple[float, ProtocolDoc, List[str]]] = []
    for doc in docs:
        score, matched = _score_doc(doc, merged, normalized, vitals)
        ranked.append((score, doc, matched))
    ranked.sort(key=lambda x: x[0], reverse=True)

    primary_doc = ranked[0][1] if ranked else None
    primary_score = ranked[0][0] if ranked else 0.0
    primary_matched = ranked[0][2] if ranked else []

    secondary: List[str] = []
    for s, d, _m in ranked[1:top_k + 1]:
        if s > 0 and (primary_score <= 0 or s >= 0.45 * primary_score):
            secondary.append(d.protocol_id)
    for pid in case_result.get("top_case_protocols", [])[:2]:
        if pid and pid != (primary_doc.protocol_id if primary_doc else "") and pid not in secondary:
            secondary.append(pid)

    evidence_refs: List[Dict[str, Any]] = []
    for s, d, m in ranked[:top_k + 1]:
        if s <= 0:
            continue
        evidence_refs.append(
            {
                "protocol_id": d.protocol_id,
                "section": "keywords+rules",
                "score": round(s, 3),
                "matched": m[:6],
            }
        )
    evidence_refs.extend(case_result.get("case_refs", []))

    if not primary_doc:
        return {
            "primary_protocol_id": "chest_pain",
            "secondary_protocol_ids": [],
            "matched_keywords": [],
            "normalized_complaints": normalized,
            "red_flag_union": [],
            "evidence_refs": [],
            "retrieval_score": 0.0,
            "fallback_used": bool(case_result.get("fallback_used", True)),
            "protocol_doc": {},
            "case_result": case_result,
        }

    red_union = list(primary_doc.red_flags)
    for sid in secondary:
        for d in docs:
            if d.protocol_id == sid:
                for rf in d.red_flags:
                    if rf not in red_union:
                        red_union.append(rf)
    for rf in case_result.get("risk_flags", []):
        if rf not in red_union:
            red_union.append(rf)

    return {
        "primary_protocol_id": primary_doc.protocol_id,
        "secondary_protocol_ids": secondary,
        "matched_keywords": primary_matched,
        "normalized_complaints": normalized,
        "red_flag_union": red_union,
        "evidence_refs": evidence_refs,
        "retrieval_score": round(primary_score, 3),
        "fallback_used": (primary_score <= 0) and bool(case_result.get("fallback_used", True)),
        "protocol_doc": {
            "protocol_id": primary_doc.protocol_id,
            "version": primary_doc.version,
            "required_slots": list(primary_doc.required_slots),
            "questions": list(primary_doc.questions),
            "urgency_rules": list(primary_doc.urgency_rules),
        },
        "case_result": case_result,
    }
