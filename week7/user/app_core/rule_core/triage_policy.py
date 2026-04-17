from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

CN_AD_TO_CTAS_COMPAT = {"A": 1, "B": 2, "C": 3, "D": 4}
LEVEL_BY_ACUITY = {"A": 1, "B": 2, "C": 3, "D": 4}
ZONE_BY_LEVEL = {1: "red", 2: "red", 3: "yellow", 4: "green"}
MAX_WAIT_MINUTES_BY_LEVEL = {1: 0, 2: 10, 3: 30, 4: 120}


@dataclass(frozen=True)
class TriageInput:
    chief_complaint: str
    symptoms: List[str]
    vitals: Dict[str, float]
    arrival_mode: str = "walk-in"


@dataclass(frozen=True)
class TriageDecision:
    acuity_ad: str
    level_1_4: int
    ctas_compat: int
    zone: str
    green_channel: bool
    required_resources_count: int
    max_wait_minutes: int
    hooks: Set[str]


def _contains_any(texts: Iterable[str], keywords: Iterable[str]) -> bool:
    merged = " ".join(texts).lower()
    return any(keyword in merged for keyword in keywords)


def _estimate_required_resources_count(texts: List[str]) -> int:
    """
    Deterministic proxy for resource demand.
    """
    score = 0
    if _contains_any(texts, ["ct", "x-ray", "xray", "mri", "imaging"]):
        score += 1
    if _contains_any(texts, ["cbc", "blood test", "lab"]):
        score += 1
    if _contains_any(texts, ["iv", "oxygen"]):
        score += 1
    if _contains_any(texts, ["suture", "fracture", "procedure"]):
        score += 1
    return score


def triage_cn_ad(case: TriageInput) -> TriageDecision:
    texts = [case.chief_complaint, *case.symptoms]
    hooks: Set[str] = set()

    spo2 = float(case.vitals.get("spo2", 100))
    sbp = float(case.vitals.get("sbp", 120))

    has_chest_pain = _contains_any(texts, ["chest pain", "胸痛", "胸口疼", "胸闷"])
    has_diaphoresis = _contains_any(texts, ["diaphoresis", "cold sweat", "冷汗", "大汗"])
    has_stroke_fast = _contains_any(texts, ["fast positive", "stroke", "中风", "口角歪", "单侧无力", "言语不清"])
    has_severe_dyspnea = _contains_any(texts, ["severe dyspnea", "cannot breathe", "shortness of breath", "呼吸困难", "喘不上气"])
    has_mild_sprain = _contains_any(texts, ["mild sprain", "ankle sprain", "轻微扭伤"])
    has_trauma = _contains_any(texts, ["trauma", "injury", "fracture", "fall", "外伤", "骨折", "摔伤"])
    has_unresponsive = _contains_any(texts, ["unresponsive", "coma", "昏迷", "无反应", "意识不清"])
    has_shock = _contains_any(texts, ["shock", "休克"])
    has_active_seizure = _contains_any(texts, ["seizure", "convulsion", "抽搐", "癫痫发作"])
    has_anaphylaxis = _contains_any(texts, ["anaphylaxis", "allergic reaction", "喉头水肿", "过敏性休克"])
    has_headache_redflag = _contains_any(texts, ["worst headache", "sudden severe headache", "突发剧烈头痛", "最严重头痛"])
    resource_count = _estimate_required_resources_count(texts)

    if spo2 < 90 or sbp < 90:
        hooks.add("abnormal_vitals")

    if spo2 < 85 or sbp < 80:
        hooks.update({"green_channel", "deterioration"})
        acuity = "A"
    elif has_unresponsive or has_shock or has_active_seizure:
        hooks.update({"green_channel", "deterioration"})
        acuity = "A"
    elif has_anaphylaxis or has_headache_redflag:
        hooks.add("green_channel")
        acuity = "B"
    elif has_trauma or (has_chest_pain and has_diaphoresis) or has_stroke_fast:
        hooks.add("green_channel")
        acuity = "B"
    elif has_severe_dyspnea or "abnormal_vitals" in hooks:
        acuity = "B"
    elif resource_count >= 2:
        acuity = "C"
    elif has_mild_sprain:
        acuity = "D"
    else:
        acuity = "C"

    level = LEVEL_BY_ACUITY[acuity]
    if acuity == "D" and resource_count >= 2:
        level = 3
    zone = ZONE_BY_LEVEL[level]
    max_wait = MAX_WAIT_MINUTES_BY_LEVEL[level]
    if zone == "yellow":
        hooks.add("wait_cap_30m")

    return TriageDecision(
        acuity_ad=acuity,
        level_1_4=level,
        ctas_compat=CN_AD_TO_CTAS_COMPAT[acuity],
        zone=zone,
        green_channel=("green_channel" in hooks),
        required_resources_count=resource_count,
        max_wait_minutes=max_wait,
        hooks=hooks,
    )
