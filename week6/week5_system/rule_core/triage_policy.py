from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

CN_AD_TO_CTAS_COMPAT = {"A": 1, "B": 2, "C": 3, "D": 4}
ZONE_BY_ACUITY = {"A": "red", "B": "yellow", "C": "yellow", "D": "green"}


@dataclass(frozen=True)
class TriageInput:
    chief_complaint: str
    symptoms: List[str]
    vitals: Dict[str, float]
    arrival_mode: str = "walk-in"


@dataclass(frozen=True)
class TriageDecision:
    acuity_ad: str
    ctas_compat: int
    zone: str
    hooks: Set[str]


def _contains_any(texts: Iterable[str], keywords: Iterable[str]) -> bool:
    merged = " ".join(texts).lower()
    return any(keyword in merged for keyword in keywords)


def triage_cn_ad(case: TriageInput) -> TriageDecision:
    texts = [case.chief_complaint, *case.symptoms]
    hooks: Set[str] = set()

    spo2 = float(case.vitals.get("spo2", 100))
    sbp = float(case.vitals.get("sbp", 120))

    has_chest_pain = _contains_any(texts, ["chest pain", "胸痛"])
    has_diaphoresis = _contains_any(texts, ["diaphoresis", "cold sweat", "出汗", "冷汗"])
    has_stroke_fast = _contains_any(texts, ["fast positive", "卒中", "言语不清", "偏瘫"])
    has_severe_dyspnea = _contains_any(texts, ["severe dyspnea", "cannot breathe", "呼吸困难"])
    has_mild_sprain = _contains_any(texts, ["mild sprain", "ankle sprain", "轻度扭伤"])

    if spo2 < 90 or sbp < 90:
        hooks.add("abnormal_vitals")

    if (has_chest_pain and has_diaphoresis) or has_stroke_fast:
        hooks.add("green_channel")
        acuity = "A"
    elif has_severe_dyspnea or "abnormal_vitals" in hooks:
        acuity = "B"
    elif has_mild_sprain:
        acuity = "D"
    else:
        acuity = "C"

    return TriageDecision(
        acuity_ad=acuity,
        ctas_compat=CN_AD_TO_CTAS_COMPAT[acuity],
        zone=ZONE_BY_ACUITY[acuity],
        hooks=hooks,
    )
