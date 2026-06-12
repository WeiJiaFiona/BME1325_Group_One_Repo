from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class FullViewDecision:
    event_id: str
    to_room_id: str
    disposition: str
    sync_reason: str


def compute_mews(vitals: Dict[str, Any] | None) -> int:
    readings = dict(vitals or {})
    score = 0
    rr = _to_float(readings.get("resp_rate") or readings.get("rr"))
    hr = _to_float(readings.get("heart_rate") or readings.get("hr") or readings.get("pulse"))
    sbp = _to_float(readings.get("sbp") or readings.get("systolic_bp"))
    spo2 = _to_float(readings.get("spo2"))
    temp = _to_float(readings.get("temperature") or readings.get("temp"))
    avpu = str(readings.get("avpu") or readings.get("mental_status") or "").strip().lower()
    if rr is not None:
        if rr <= 8 or rr >= 30:
            score += 3
        elif rr >= 21:
            score += 2
        elif rr <= 14:
            score += 1
    if hr is not None:
        if hr <= 40 or hr >= 130:
            score += 3
        elif hr >= 111:
            score += 2
        elif hr <= 50 or hr >= 101:
            score += 1
    if sbp is not None:
        if sbp <= 70:
            score += 3
        elif sbp <= 80 or sbp >= 200:
            score += 2
        elif sbp <= 100:
            score += 1
    if temp is not None and (temp < 35 or temp >= 38.5):
        score += 2
    if spo2 is not None:
        if spo2 < 90:
            score += 3
        elif spo2 < 93:
            score += 2
    if avpu in {"p", "u", "pain", "unresponsive"}:
        score += 3
    elif avpu in {"v", "voice"}:
        score += 1
    return score


def danger_tier(vitals: Dict[str, Any] | None) -> str:
    readings = dict(vitals or {})
    sbp = _to_float(readings.get("sbp") or readings.get("systolic_bp"))
    spo2 = _to_float(readings.get("spo2"))
    rr = _to_float(readings.get("resp_rate") or readings.get("rr"))
    if (spo2 is not None and spo2 < 90) or (sbp is not None and sbp < 90) or (rr is not None and rr >= 30):
        return "critical"
    if (spo2 is not None and spo2 < 93) or (sbp is not None and sbp < 100):
        return "unstable"
    return "stable"


def decide_ed_disposition(*, acuity: str | None, ctas: Any, vitals: Dict[str, Any] | None) -> FullViewDecision:
    acuity_value = str(acuity or "").strip().upper()
    ctas_level = _to_int(ctas, 3)
    mews = compute_mews(vitals)
    tier = danger_tier(vitals)
    if acuity_value in {"A", "B"} or ctas_level <= 1 or mews >= 5 or tier == "critical":
        return FullViewDecision(
            event_id="TRANSFER_ED_TO_ICU",
            to_room_id="icu_admission",
            disposition="ICU",
            sync_reason="disposition_to_icu",
        )
    if acuity_value == "C" or ctas_level <= 3 or mews >= 2 or tier == "unstable":
        return FullViewDecision(
            event_id="TRANSFER_ED_TO_WARD",
            to_room_id="ward_admission",
            disposition="WARD",
            sync_reason="disposition_to_ward",
        )
    return FullViewDecision(
        event_id="ED_PATIENT_EXIT_HOSPITAL",
        to_room_id="exit",
        disposition="DISCHARGE",
        sync_reason="disposition_to_discharge",
    )


def diagnostic_decision() -> FullViewDecision:
    return FullViewDecision(
        event_id="ED_TO_DIAGNOSTIC_MOVE",
        to_room_id="ed_diagnostic",
        disposition="DIAGNOSTIC",
        sync_reason="doctor_ordered_test",
    )


def discharge_decision() -> FullViewDecision:
    return FullViewDecision(
        event_id="ED_PATIENT_EXIT_HOSPITAL",
        to_room_id="exit",
        disposition="DISCHARGE",
        sync_reason="disposition_to_discharge",
    )


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
