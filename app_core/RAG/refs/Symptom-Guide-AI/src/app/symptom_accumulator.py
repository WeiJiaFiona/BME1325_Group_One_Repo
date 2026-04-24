"""
Cross-turn compound red flag detection for SymptoGuide AI.

Scans ALL accumulated user symptoms across the conversation to detect
compound danger patterns that individually appear harmless but together
indicate a medical emergency (e.g., heart attack, stroke, sepsis).

This module runs BEFORE intent classification on every user message.
"""

import re
import logging
from typing import Optional, List, Dict

logger = logging.getLogger("SymptoGuide")


# ============================================================================
#  COMPOUND DANGER PATTERNS
# ============================================================================
# Each pattern defines:
#   - name: display name for the alert
#   - min_match: minimum number of symptom groups that must match
#   - groups: list of symptom groups; each group is a list of regex patterns
#     that count as one "signal"
#   - alert_message: the emergency instruction shown to the user

COMPOUND_PATTERNS: List[Dict] = [
    {
        "name": "Possible Cardiac Event (Heart Attack)",
        "min_match": 3,
        "groups": [
            # Group 1: Left arm / arm pain or heaviness
            [r"\bleft\s*arm\b", r"\barm.{0,20}(pain|heavy|heav|numb|weak|tingl)\w*\b",
             r"\b(pain|heavy|heav|numb|weak|tingl)\w*.{0,20}\barm\b"],
            # Group 2: Chest symptoms
            [r"\bchest.{0,20}(pain|tight|press|heavy|crush|discomfort)\w*\b",
             r"\b(pain|tight|press|heavy|crush|discomfort)\w*.{0,20}\bchest\b"],
            # Group 3: Jaw / neck pain
            [r"\bjaw.{0,20}(pain|ache|aching|hurt)\w*\b",
             r"\b(ache|aching|pain|hurt)\w*.{0,20}\bjaw\b",
             r"\bjaw\b"],
            # Group 4: Sweating / cold sweat
            [r"\bsweat(ing|s|y)?\b", r"\bcold\s*sweat\b",
             r"\bperspir(ing|ation)\b"],
            # Group 5: Shortness of breath
            [r"\b(short(ness)?|difficult(y)?)\s*(of\s*)?breath\b",
             r"\bcan'?t\s*breathe\b"],
            # Group 6: Nausea / lightheaded
            [r"\bnause(a|ous)\b", r"\blightheaded\b", r"\bdizz(y|iness)\b"],
        ],
    },
    {
        "name": "Possible Stroke (FAST Signs)",
        "min_match": 2,
        "groups": [
            # Group 1: Face drooping / numbness
            [r"\bface.{0,20}(droop|numb|weak|tingle)\w*\b",
             r"\b(droop|numb)\w*.{0,20}face\b",
             r"\bfacial.{0,20}(droop|numb|weak)\w*\b"],
            # Group 2: Arm weakness
            [r"\barm.{0,20}(weak|numb|can'?t|unable)\w*\b",
             r"\b(weak|numb)\w*.{0,20}arm\b",
             r"\bcan'?t.{0,20}(lift|move|raise).{0,10}arm\b"],
            # Group 3: Speech difficulty
            [r"\b(slur(red|ring)?).{0,15}(speak|talk|speech|words?)\b",
             r"\bspeech.{0,15}(slur|difficult)\w*\b",
             r"\btrouble.{0,15}(speak|talk)\w*\b",
             r"\bspeech\b.*\bslur\w*\b",
             r"\bslur\w*\b"],
            # Group 4: Sudden severe headache
            [r"\bsudden.{0,10}(severe\s*)?headache\b",
             r"\bworst\s*headache\b"],
            # Group 5: Vision loss
            [r"\b(vision|sight).{0,15}(loss|blur|double)\b",
             r"\bblur(red|ry)?\s*(vision|sight)\b"],
            # Group 6: Confusion
            [r"\bconfus(ed|ion)\b", r"\bdisoriented\b"],
        ],
    },
    {
        "name": "Possible Sepsis",
        "min_match": 3,
        "groups": [
            # Group 1: High fever / chills
            [r"\b(high\s*)?fever\b", r"\bchills\b", r"\bshiver(ing|s)?\b"],
            # Group 2: Confusion / disorientation
            [r"\bconfus(ed|ion)\b", r"\bdisoriented\b",
             r"\b(can'?t|not)\s*(think|focus)\s*(clear|straight)\b"],
            # Group 3: Rapid heart / breathing
            [r"\brapid\s*(heart|pulse|breathing)\b",
             r"\bheart\s*(rac|pound|fast)\w*\b",
             r"\btachycardi\w*\b"],
            # Group 4: Skin changes
            [r"\bskin\s*(mottle|cold|clam|pale|blue|discolor)\w*\b",
             r"\b(mottled|clammy|blotch)\w*\s*skin\b"],
            # Group 5: Severe pain / feeling very unwell
            [r"\bworst\s*(I'?ve\s*)?(ever\s*)?felt\b",
             r"\bfeel(ing)?\s*(terrible|awful|very\s*sick|like\s*dying)\b"],
        ],
    },
    {
        "name": "Possible Anaphylaxis",
        "min_match": 2,
        "groups": [
            # Group 1: Swelling (throat, tongue, lips, face)
            [r"\b(throat|tongue|lip|face)\s*(swell|swollen|puff)\w*\b",
             r"\bswell(ing|ed)?\s*(throat|tongue|lip|face)\b"],
            # Group 2: Breathing difficulty
            [r"\b(can'?t|difficult|hard|trouble)\s*(breathe|breathing)\b",
             r"\bwheezing\b"],
            # Group 3: Rash / hives
            [r"\bhives\b", r"\brash\b.*\b(spread|all\s*over)\b"],
            # Group 4: Dizziness / fainting
            [r"\b(dizz|faint|pass(ed|ing)?\s*out)\w*\b"],
        ],
    },
]


# ============================================================================
#  ACCUMULATOR
# ============================================================================

def check_compound_emergency(messages: list) -> Optional[Dict]:
    """
    Scan ALL user messages in the conversation for compound danger patterns.

    Parameters
    ----------
    messages : list
        The full ``st.session_state.messages`` list with ``role`` and ``content``.

    Returns
    -------
    dict or None
        ``{"name": ..., "matched_groups": ..., "call_to_action": ...}``
        if a compound pattern is detected, else ``None``.
    """
    # Combine all user messages into one block for scanning
    user_text = " ".join(
        msg.get("content", "")
        for msg in messages
        if msg.get("role") == "user"
    ).lower()

    if not user_text.strip():
        return None

    for pattern in COMPOUND_PATTERNS:
        matched_groups = []
        for group in pattern["groups"]:
            for regex in group:
                if re.search(regex, user_text):
                    matched_groups.append(group)
                    break  # one match per group is enough

        if len(matched_groups) >= pattern["min_match"]:
            logger.warning(
                f"COMPOUND EMERGENCY DETECTED: {pattern['name']} "
                f"({len(matched_groups)}/{len(pattern['groups'])} groups matched)"
            )
            return {
                "name": pattern["name"],
                "matched_groups": len(matched_groups),
                "total_groups": len(pattern["groups"]),
                "call_to_action": _get_call_to_action(pattern["name"]),
            }

    return None


def _get_call_to_action(pattern_name: str) -> str:
    """Return the appropriate emergency call-to-action text."""
    actions = {
        "Possible Cardiac Event (Heart Attack)": (
            "🚨 **EMERGENCY WARNING** 🚨\n\n"
            "The combination of symptoms you have described across our conversation "
            "(left arm heaviness/pain, jaw ache, and sweating) are **classic warning signs "
            "of a heart attack**.\n\n"
            "**Please take these steps IMMEDIATELY:**\n"
            "1. **Call emergency services (911 / 999 / 112)** right now\n"
            "2. **Chew an aspirin** (300mg) if you have one and are not allergic\n"
            "3. **Sit down and rest** — do not exert yourself\n"
            "4. **Unlock your front door** so paramedics can reach you\n\n"
            "⏱️ **Time is critical.** Every minute matters for heart attacks.\n\n"
            "Do NOT wait to see if symptoms improve. Call for help NOW."
        ),
        "Possible Stroke (FAST Signs)": (
            "🚨 **EMERGENCY WARNING — Possible Stroke** 🚨\n\n"
            "The symptoms you have described match the **FAST warning signs of a stroke**:\n"
            "- **F**ace drooping\n"
            "- **A**rm weakness\n"
            "- **S**peech difficulty\n"
            "- **T**ime to call emergency services\n\n"
            "**Call emergency services (911 / 999 / 112) IMMEDIATELY.**\n"
            "Note the exact time symptoms started — doctors need this information.\n\n"
            "⏱️ **Every minute without treatment increases brain damage.**"
        ),
        "Possible Sepsis": (
            "🚨 **URGENT WARNING — Possible Sepsis** 🚨\n\n"
            "The combination of your symptoms (fever, confusion, rapid heart rate) "
            "could indicate **sepsis**, a life-threatening medical emergency.\n\n"
            "**Go to the nearest Emergency Room IMMEDIATELY** or call emergency services.\n"
            "Tell them: \"I think I might have sepsis.\"\n\n"
            "⏱️ Sepsis can deteriorate rapidly. Do not delay."
        ),
        "Possible Anaphylaxis": (
            "🚨 **EMERGENCY WARNING — Possible Anaphylaxis** 🚨\n\n"
            "Swelling, breathing difficulty, and other symptoms suggest a severe "
            "allergic reaction (anaphylaxis).\n\n"
            "**Call emergency services (911 / 999 / 112) IMMEDIATELY.**\n"
            "If you have an **EpiPen**, use it now.\n"
            "Lie down with your legs elevated unless you are having trouble breathing."
        ),
    }
    return actions.get(pattern_name, "🚨 **Please call emergency services immediately.**")
