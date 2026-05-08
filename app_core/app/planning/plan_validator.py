from __future__ import annotations

from typing import Any, Dict, List


_URGENCY_LEVEL = {"ROUTINE": 0, "URGENT": 1, "RESUS": 2}
_DISPOSITION_LEVEL = {"OUTPATIENT": 0, "OBSERVE": 1, "WARD": 2, "ICU": 3}


def _normalize_single_question(text: str) -> str:
    line = (text or "").strip().splitlines()[0].strip()
    if not line:
        return "When did the symptom start?"
    if line.count("?") + line.count("？") > 1:
        for token in ["?", "？"]:
            idx = line.find(token)
            if idx >= 0:
                return line[: idx + 1]
    if "?" not in line and "？" not in line:
        return f"{line.rstrip('.。!！')}?"
    return line


def validate_plan(
    *,
    plan_contract: Dict[str, Any],
    retrieval_result: Dict[str, Any],
    vitals: Dict[str, Any],
) -> Dict[str, Any]:
    warnings: List[str] = []
    hard_override = False

    required = [
        "primary_question",
        "patient_utterance",
        "urgency_floor",
        "urgency_proposed",
        "disposition_floor",
        "disposition_proposed",
        "language",
    ]
    for field in required:
        if field not in plan_contract:
            warnings.append(f"MISSING_{field.upper()}")

    q = dict(plan_contract.get("primary_question", {}))
    q_text = _normalize_single_question(str(q.get("text", "")))
    q["text"] = q_text
    plan_contract["primary_question"] = q

    floor_u = str(plan_contract.get("urgency_floor", "ROUTINE")).upper()
    prop_u = str(plan_contract.get("urgency_proposed", floor_u)).upper()
    floor_d = str(plan_contract.get("disposition_floor", "OUTPATIENT")).upper()
    prop_d = str(plan_contract.get("disposition_proposed", floor_d)).upper()

    if _URGENCY_LEVEL.get(prop_u, 0) < _URGENCY_LEVEL.get(floor_u, 0):
        prop_u = floor_u
        hard_override = True
        warnings.append("HARD_OVERRIDE_URGENCY_FLOOR")
    if _DISPOSITION_LEVEL.get(prop_d, 0) < _DISPOSITION_LEVEL.get(floor_d, 0):
        prop_d = floor_d
        hard_override = True
        warnings.append("HARD_OVERRIDE_DISPOSITION_FLOOR")

    spo2 = float(vitals.get("spo2", 97) or 97)
    sbp = float(vitals.get("sbp", 120) or 120)
    critical = (spo2 < 90) or (sbp < 90) or (retrieval_result.get("primary_protocol_id") == "stroke")
    if critical and prop_u != "RESUS":
        prop_u = "RESUS"
        prop_d = "ICU"
        hard_override = True
        warnings.append("HARD_OVERRIDE_CRITICAL_SAFETY")

    plan_contract["urgency_proposed"] = prop_u
    plan_contract["disposition_proposed"] = prop_d

    result = "hard_override" if hard_override else ("soft_override" if warnings else "pass")
    return {
        "plan_contract": plan_contract,
        "validator_result": result,
        "warning_codes": warnings,
        "override_applied": bool(warnings),
        "fallback_used": False,
    }
