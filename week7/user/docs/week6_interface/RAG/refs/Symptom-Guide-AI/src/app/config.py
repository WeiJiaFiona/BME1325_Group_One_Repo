"""
Configuration and constants for SymptoGuide AI.
"""

from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path

# load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv()

# ============================================================================
#  PROJECT PATHS
# ============================================================================

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]


@dataclass
class MedicalConfig:
    """Configuration for medical AI system."""
    DB_DIR: str = str(PROJECT_ROOT / "chroma_db")
    LOG_DIR: str = str(PROJECT_ROOT / "logs")
    
    # Models
    LLM_MODEL: str = "llama3"
    EMBED_MODEL: str = "BAAI/bge-large-en-v1.5"
    
    # UI Settings
    PAGE_TITLE: str = "SymptoGuide Smart"
    PAGE_ICON: str = "🩺"


# ============================================================================
#  EMERGENCY KEYWORDS & PATTERNS
# ============================================================================

EMERGENCY_PATTERNS: List[Dict[str, any]] = [
    {"keywords": ["difficulty breathing", "trouble breathing", "choking", "gasping", "can't breathe", "cannot breathe"], "alert": "Airway Emergency"},
    {"keywords": ["chest pain", "crushing chest", "heart attack"], "alert": "Possible Cardiac Event"},
    {"keywords": ["severe bleeding", "heavy bleeding", "hemorrhage", "won't stop bleeding"], "alert": "Severe Bleeding"},
    {"keywords": ["unconscious", "stroke", "seizure"], "alert": "Neurological Emergency"},
    {"keywords": ["suicide", "kill myself"], "alert": "Mental Health Crisis"}
]

FUZZY_EMERGENCY_PATTERNS = [
    r"chest\s+(pain|hurt|crush|tight|heavy|pressure)",
    r"(can't|cannot|hard|difficult|stop|short).{0,15}(breath|breathing)"
]


# ============================================================================
#  PROMPT TEMPLATES
# ============================================================================

# --- Simple extraction prompts (use build_chain) ---

INTENT_CLASSIFICATION_PROMPT = """
Classify the user input into exactly one category:
1. GREETING: Greetings or pleasantries (e.g., "Hi", "hello", "thanks", "bye").
2. SYMPTOM: Medical complaints containing actionable details (e.g., "I have a sharp headache", "head 2days fever").
3. VAGUE: Single words, isolated body parts without symptoms (e.g., "head", "it hurts", "leg").
4. OFF_TOPIC: Non-medical queries (e.g., weather, coding, jokes).
5. SUMMARY: User asking for recap or diagnosis (e.g., "what do i suffer from", "summarize my symptoms").

User Input: "{input}"

Output ONLY the category name.
"""

SYMPTOM_ACCUMULATION_PROMPT = """
Read the conversation and extract ALL medical symptoms the user mentioned.
Combine into ONE search string for a medical database.

CONVERSATION:
{chat_history}

CURRENT MESSAGE: {input}

Rules:
1. Include symptoms from ALL messages, not just the latest.
2. If user corrected themselves, use the CORRECTED version only.
3. Include details: location, duration, severity.
4. Output a single search phrase. Example: "left-sided headache 3 days with fever"
5. If NO medical symptoms at all, output: NONE

Search string:
"""

QUERY_ENHANCEMENT_PROMPT = """
Convert user symptoms into a precise medical search string.
Input: "{input}"
Rules:
1. Correct typos ("fevar" -> "fever").
2. Translate vague terms ("head" -> "headache").
3. Combine ALL symptoms ("headache and fever").
4. Output ONLY the search string.

Search String:
"""

# --- Conversational prompts (use build_chat_chain) ---

# SYSTEM_IDENTITY: sent as SystemMessage — the AI's personality and rules.
SYSTEM_IDENTITY = """You are a warm, knowledgeable medical assistant in an ongoing conversation.

CRITICAL OUTPUT RULES:
- Start EVERY response with actual content. Never start with labels, stage names, or meta-text.
- NEVER output words like "Gathering", "Ready", "Followup", "Greeting" at the start.
- NEVER say "I acknowledge", "I understand", "What's going on?", or any filler phrase.
- NEVER introduce yourself. Never say "Hello! I'm..." or "I'm a medical assistant".
- NEVER repeat anything you already said in previous turns.
- NEVER mention databases, searches, or internal processes.
- NEVER invent symptoms the user did not say.
- NEVER mention rare diseases for common symptoms.
- NEVER re-summarize symptoms you already discussed. Add NEW content only.
- Short answers ("left", "2 days", "severe") are valid. Use them, don't re-ask.
- If user says "no" or "nothing else" — provide your assessment immediately.

STYLE:
- Warm, professional — like a trusted nurse.
- Use **bold** headers, bullet points for lists.
- Jump straight to content. No filler, no preamble, no repetition."""

# HUMAN_TEMPLATE: sent as HumanMessage — the context for this specific turn.
HUMAN_TEMPLATE = """Previous conversation:
{recent_chat}

Symptoms collected so far: {symptoms_so_far}

Medical knowledge:
{context}

User just said: {input}

Instructions for this turn: {stage}"""

# Stage-specific instruction strings (injected into the {stage} slot)
STAGE_GREETING = """The user greeted you. Respond with one warm sentence asking what symptoms they have. Example: "Hey! What symptoms are you experiencing today?" — nothing more."""

STAGE_GATHERING = """The user just told you their symptoms but you need more details. Ask ALL your remaining questions in ONE short numbered list. Check what you already know from "Symptoms collected so far" and ONLY ask about what's missing from: duration, location, severity, other symptoms. Do NOT explain anything yet. Just ask the questions."""

STAGE_READY = """You have enough symptom details. Give your FULL medical assessment now. Use the medical knowledge section to inform your response. Structure it exactly like this:

**What this could be**
2-3 likely conditions. For each: what it is, why it fits, how common it is.

**What you can do at home**
5-6 specific tips: OTC meds by name (paracetamol, ibuprofen), home remedies, rest advice, foods to eat/avoid.

**Watch for these warning signs** ⚠️
2-3 specific signs needing a doctor. Be precise (e.g., "fever above 39.5°C not responding to paracetamol").

Feel free to ask if you have more questions!"""

STAGE_FOLLOWUP = """An assessment was already given. The user is saying something new. Respond naturally and briefly:
- If they mention a new symptom: note it and update your advice.
- If they say something casual ("hi", "thanks"): respond warmly in 1 sentence, ask if they have other symptoms.
- If they ask a question: answer it directly without repeating previous info.
- If they say something unrelated to health ("i need to sleep"): respond naturally, tie it back to their health if relevant (e.g., "Rest is great for recovery").
NEVER repeat your previous assessment. Keep it short and natural."""

# Backward compatibility aliases
SYSTEM_PROMPT = SYSTEM_IDENTITY + "\n" + HUMAN_TEMPLATE
DIAGNOSIS_PROMPT = SYSTEM_PROMPT
KEYWORD_EXTRACTION_PROMPT = SYMPTOM_ACCUMULATION_PROMPT
