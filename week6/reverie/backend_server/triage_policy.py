"""
Triage/routing helpers that can be reused by EDSim agents.

Design goals:
- Keep compatibility with existing CTAS-based flow.
- Allow CN A-D style acuity input when provided.
- Provide deterministic fallback when CTAS is missing.
"""

from typing import Any, Dict, Optional


_GREEN_CHANNEL_KEYWORDS = ("胸痛", "卒中", "中风", "创伤", "大出血", "休克")
_CRITICAL_KEYWORDS = ("意识障碍", "呼吸困难", "心脏骤停", "呼吸骤停", "休克")
_URGENT_KEYWORDS = ("胸痛", "卒中", "中风", "高热", "剧烈疼痛", "呕血")

_AD_TO_CTAS = {"A": 1, "B": 2, "C": 3, "D": 4}
_CTAS_TO_ED_ZONE = {
    1: "trauma room",
    2: "major injuries zone",
    3: "minor injuries zone",
    4: "minor injuries zone",
    5: "minor injuries zone",
}


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def detect_abnormal_vitals(vitals: Dict[str, Any]) -> bool:
    spo2 = _to_float(vitals.get("spo2", 100), 100)
    sbp = _to_float(vitals.get("sbp", 120), 120)
    hr = _to_float(vitals.get("hr", 80), 80)
    rr = _to_float(vitals.get("rr", 16), 16)
    return spo2 < 94 or sbp < 90 or hr > 130 or rr > 30


def classify_ad_level(snapshot: Dict[str, Any]) -> str:
    complaint = str(snapshot.get("chief_complaint", "") or "")
    vitals = snapshot.get("vitals", {}) or {}
    resource_need = _safe_int(snapshot.get("resource_need", 1), 1)

    spo2 = _to_float(vitals.get("spo2", 100), 100)
    sbp = _to_float(vitals.get("sbp", 120), 120)

    if spo2 < 90 or sbp < 90 or any(k in complaint for k in _CRITICAL_KEYWORDS):
        return "A"
    if detect_abnormal_vitals(vitals) or any(k in complaint for k in _URGENT_KEYWORDS):
        return "B"
    if resource_need >= 2:
        return "C"
    return "D"


def ad_to_ctas(ad_level: str) -> int:
    return _AD_TO_CTAS.get(str(ad_level).upper(), 3)


def ctas_to_ed_zone(ctas: int) -> str:
    return _CTAS_TO_ED_ZONE.get(_safe_int(ctas, 3), "minor injuries zone")


def detect_escalation_hooks(snapshot: Dict[str, Any]) -> list:
    hooks = []
    complaint = str(snapshot.get("chief_complaint", "") or "")
    vitals = snapshot.get("vitals", {}) or {}
    if detect_abnormal_vitals(vitals):
        hooks.append("abnormal_vitals")
    if any(k in complaint for k in _GREEN_CHANNEL_KEYWORDS):
        hooks.append("green_channel")
    if snapshot.get("deterioration"):
        hooks.append("deterioration")
    if snapshot.get("consult_required"):
        hooks.append("consult_required")
    if snapshot.get("icu_required"):
        hooks.append("icu_required")
    if snapshot.get("surgery_required"):
        hooks.append("surgery_required")
    return hooks


def resolve_patient_priority_and_zone(patient_obj: Any, triage_standard: str = "CN_AD") -> Dict[str, Any]:
    """
    Resolve CTAS priority and ED zone for a patient-like object.

    Accepted inputs:
    - EDSim patient object with .scratch
    - dict-like snapshot
    """
    scratch = getattr(patient_obj, "scratch", None)
    if scratch is not None:
        snapshot = {
            "chief_complaint": getattr(scratch, "chief_complaint", ""),
            "vitals": getattr(scratch, "vitals", {}) or {},
            "resource_need": getattr(scratch, "resource_need", 1),
            "deterioration": getattr(scratch, "deterioration", False),
            "consult_required": getattr(scratch, "consult_required", False),
            "icu_required": getattr(scratch, "icu_required", False),
            "surgery_required": getattr(scratch, "surgery_required", False),
        }
        existing_ctas = getattr(scratch, "CTAS", None)
        existing_ad = getattr(scratch, "acuity_ad", None)
    else:
        snapshot = patient_obj if isinstance(patient_obj, dict) else {}
        existing_ctas = snapshot.get("CTAS")
        existing_ad = snapshot.get("acuity_ad")

    ctas = _safe_int(existing_ctas, 0)
    ad_level = str(existing_ad).upper() if existing_ad else None

    if ctas <= 0:
        standard = (triage_standard or "CN_AD").upper()
        if standard == "CTAS_COMPAT":
            ad_level = classify_ad_level(snapshot)
            ctas = ad_to_ctas(ad_level)
        else:
            if ad_level not in _AD_TO_CTAS:
                ad_level = classify_ad_level(snapshot)
            ctas = ad_to_ctas(ad_level)
    if ad_level not in _AD_TO_CTAS:
        ad_level = {1: "A", 2: "B", 3: "C", 4: "D", 5: "D"}.get(ctas, "C")

    return {
        "ctas": ctas,
        "acuity_ad": ad_level,
        "injuries_zone": ctas_to_ed_zone(ctas),
        "escalation_hooks": detect_escalation_hooks(snapshot),
    }
