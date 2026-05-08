"""
Medical logic: emergency detection, intent classification, query enhancement.
"""

import re
import logging
from typing import Optional

from src.app.config import (
    EMERGENCY_PATTERNS,
    FUZZY_EMERGENCY_PATTERNS,
    INTENT_CLASSIFICATION_PROMPT,
    QUERY_ENHANCEMENT_PROMPT
)
from src.app.llm_utils import build_chain

logger = logging.getLogger("SymptoGuide")


def _word_boundary_match(keyword: str, text: str) -> bool:
    """Check if keyword appears as a whole word/phrase (not as a substring)."""
    pattern = r'\b' + re.escape(keyword) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def fast_emergency_check(text: str) -> Optional[str]:
    """
    Word-boundary-based check for immediate red flags.
    Returns alert message if emergency detected, None otherwise.
    Uses word-boundary matching to avoid false positives like
    'breathing normally' triggering an airway emergency.
    """
    text_lower = text.lower()

    # Check keyword patterns using word-boundary matching
    for pattern in EMERGENCY_PATTERNS:
        if any(_word_boundary_match(kw, text_lower) for kw in pattern["keywords"]):
            return pattern["alert"]

    # Regex-based fuzzy matching (already uses contextual patterns)
    for regex_pattern in FUZZY_EMERGENCY_PATTERNS:
        if re.search(regex_pattern, text, re.IGNORECASE):
            return "Emergency Detected (Fuzzy Match)"

    return None


def classify_intent(text: str) -> str:
    """
    Classify user input into: GREETING, SYMPTOM, VAGUE, or OFF_TOPIC.
    """
    chain = build_chain(INTENT_CLASSIFICATION_PROMPT, temperature=0.0)
    intent = chain.invoke({"input": text}).strip().upper()

    logger.info(f"Intent Detected: {intent}")

    # Normalize intent
    if "GREETING" in intent:
        return "GREETING"
    elif "SYMPTOM" in intent:
        return "SYMPTOM"
    elif "VAGUE" in intent:
        return "VAGUE"
    else:
        return "OFF_TOPIC"


def enhance_query(text: str) -> str:
    """
    Convert user symptom input into a clean medical search query.
    """
    chain = build_chain(QUERY_ENHANCEMENT_PROMPT, temperature=0.1)
    enhanced = chain.invoke({"input": text}).strip()

    logger.info(f"Query Enhanced: {text} -> {enhanced}")
    return enhanced


def detect_context_request(text: str) -> bool:
    """
    Detect if user is asking about their previous symptoms/history.
    Uses multi-word phrases to avoid false positives from common words
    like 'before' or 'tell me about' that appear in normal symptom queries.
    """
    text_lower = text.lower()

    # Strong-signal phrases — each one clearly implies a history/context request
    context_phrases = [
        # Direct history references
        "chat history", "from chat", "from our chat",
        "my conversation", "our conversation",
        "info for me", "information for me",
        "know all things", "all things i have", "everything i have",

        # Explicit recap/summary requests
        "what did i tell you", "what did i say", "what did i mention",
        "what have i told", "what have i said",
        "what i said", "what i told you",
        "summarize my", "recap my", "summary of my",
        "did i tell you", "did i mention",
        "all my symptoms", "all symptoms i",
        "full history",

        # Memory references
        "do you remember", "do you recall",
        "your record", "my record",
        "my previous symptoms", "symptoms so far",
        "what do you know about me",

        # Self-diagnosis / recap questions
        "what i suffer", "what do i suffer",
        "what do i have", "what's wrong with me",
        "what is wrong with me", "my diagnosis",
        "what are my symptoms", "my health",
    ]

    return any(phrase in text_lower for phrase in context_phrases)


def extract_symptoms_from_history(messages: list) -> str:
    """
    Extract all mentioned symptoms from chat history.
    Scans BOTH user and assistant messages (the assistant often restates
    the user's symptoms).  Uses synonym mapping so shorthand like 'head'
    is captured as 'Headache'.
    Returns formatted string of all symptoms/health issues mentioned.
    """
    # Collect text from ALL messages for better coverage
    all_text_parts = []
    user_text_parts = []
    for msg in messages:
        content = msg.get("content", "")
        all_text_parts.append(content)
        if msg.get("role") == "user":
            user_text_parts.append(content)

    combined_text = " ".join(all_text_parts).lower()

    # Synonym mapping: shorthand/common words -> display label
    symptom_map = {
        # Body parts (shorthand the user may type)
        "head": "Headache",
        "stomach": "Stomach Issues",
        "throat": "Sore Throat",
        "back": "Back Pain",
        "knee": "Knee Pain",
        "eye": "Eye Problems",
        "ear": "Ear Problems",
        "tooth": "Toothache",
        "neck": "Neck Pain",
        "shoulder": "Shoulder Pain",
        "arm": "Arm Pain",
        "leg": "Leg Pain",
        "ankle": "Ankle Pain",
        "wrist": "Wrist Pain",

        # Actual symptom keywords
        "pain": "Pain",
        "ache": "Ache",
        "fever": "Fever",
        "cold": "Cold",
        "flu": "Flu",
        "cough": "Cough",
        "sneeze": "Sneezing",
        "nausea": "Nausea",
        "vomit": "Vomiting",
        "headache": "Headache",
        "migraine": "Migraine",
        "dizziness": "Dizziness",
        "fatigue": "Fatigue",
        "rash": "Rash",
        "itch": "Itching",
        "swelling": "Swelling",
        "sore": "Soreness",
        "hurt": "Pain",
        "bleeding": "Bleeding",
        "diarrhea": "Diarrhea",
        "constipation": "Constipation",
        "anxiety": "Anxiety",
        "sweat": "Sweating",
        "chills": "Chills",
        "shortness": "Shortness of Breath",
        "weakness": "Weakness",
        "tremor": "Tremor",
        "stress": "Stress",
        "tired": "Tiredness",
        "runny nose": "Runny Nose",
        "congestion": "Congestion",
        "insomnia": "Insomnia",
        "cramp": "Cramps",
        "bloating": "Bloating",
        "numbness": "Numbness",
        "tingling": "Tingling",
    }

    found_symptoms = set()
    for keyword, label in symptom_map.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
            found_symptoms.add(label)

    # Also include the raw user messages so the LLM has full context
    user_summary = "\n".join(f"- {msg}" for msg in user_text_parts if msg.strip())

    if found_symptoms:
        symptom_list = ", ".join(sorted(found_symptoms))
        return (
            f"Symptoms mentioned during this conversation:\n{symptom_list}\n\n"
            f"Raw user messages:\n{user_summary}"
        )
    return f"(No specific symptoms recorded in chat history)\n\nRaw user messages:\n{user_summary}"

