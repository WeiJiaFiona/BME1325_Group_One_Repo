from __future__ import annotations

from typing import Dict


def fallback_patient_utterance(language: str) -> str:
    if language == "zh":
        return "我先确认一个关键问题，以便尽快判断风险。"
    return "I need one key detail first so I can estimate your risk quickly."


def fallback_question(slot: str, language: str) -> str:
    zh: Dict[str, str] = {
        "duration": "症状是从什么时候开始的？",
        "worsening_pain": "和之前相比现在是否明显加重？",
        "breathing_difficulty": "现在有呼吸困难吗？",
        "radiating_pain": "疼痛有放射到手臂、下颌或背部吗？",
        "syncope": "是否有晕厥或近乎晕厥？",
        "fever": "现在是否发热？",
    }
    en: Dict[str, str] = {
        "duration": "When did the symptom start?",
        "worsening_pain": "Is it clearly worse than before?",
        "breathing_difficulty": "Are you short of breath right now?",
        "radiating_pain": "Does the pain spread to your arm, jaw, or back?",
        "syncope": "Any fainting or near-fainting?",
        "fever": "Do you have fever now?",
    }
    mapping = zh if language == "zh" else en
    return mapping.get(slot, zh["duration"] if language == "zh" else en["duration"])
