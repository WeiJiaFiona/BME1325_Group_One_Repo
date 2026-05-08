"""
SymptoGuide AI: Smart Router + Category Search
Main Streamlit UI application.
"""

import streamlit as st
import os
import sys
import logging
import base64
from pathlib import Path
import json
from datetime import datetime

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.app.config import (
    MedicalConfig, SYSTEM_IDENTITY, HUMAN_TEMPLATE,
    SYMPTOM_ACCUMULATION_PROMPT, SYSTEM_PROMPT, DIAGNOSIS_PROMPT,
    STAGE_GREETING, STAGE_GATHERING, STAGE_READY, STAGE_FOLLOWUP,
)
from src.app.llm_utils import set_mode, build_chain, build_chat_chain
from src.app.medical_logic import fast_emergency_check, classify_intent, enhance_query, detect_context_request, extract_symptoms_from_history
from src.app.vector_db import load_vector_db, smart_category_search
from src.app.symptom_accumulator import check_compound_emergency
from src.app.chat_manager import (
    create_conversation, load_conversation, save_messages,
    list_conversations, delete_conversation,
)

# ============================================================================
#  CHAT HELPERS
# ============================================================================

def format_chat_context(messages):
    """Format recent chat history as context for the LLM.
    
    The LAST message is included in full (no truncation) so the model
    sees exactly what question was asked. Older messages are truncated.
    """
    recent = messages[-10:] if len(messages) > 10 else messages
    context_lines = []
    for i, msg in enumerate(recent):
        role = "User" if msg['role'] == "user" else "Assistant"
        is_last = (i == len(recent) - 1)
        # Keep last message in full so model sees what it just asked
        if is_last:
            content = msg['content']
        else:
            content = msg['content'][:500] if len(msg['content']) > 500 else msg['content']
        context_lines.append(f"{role}: {content}")
    return "\n".join(context_lines)


# Words that are NEVER medical on their own
_CONVERSATIONAL_WORDS = {
    "hi", "hello", "hey", "yo", "thanks", "thank", "ok", "okay", "bye",
    "goodbye", "yes", "yeah", "yep", "nope", "sure", "cool", "great",
    "nice", "good", "fine", "no", "nah", "nothing", "that's it",
    "thats it", "nothing else", "no more", "hm", "hmm", "haha",
}


def is_conversational(text: str) -> bool:
    """Return True if the message is purely conversational (no medical content)."""
    cleaned = text.strip().lower().rstrip("!?.,'\"")
    # Check if entire cleaned input is a known conversational phrase
    if cleaned in _CONVERSATIONAL_WORDS:
        return True
    # Very short messages with no medical terms
    words = cleaned.split()
    if len(words) <= 2 and all(w in _CONVERSATIONAL_WORDS for w in words):
        return True
    return False


def determine_stage(messages, user_input, accumulated_symptoms, assessment_given) -> str:
    """Determine the conversation stage for the system prompt.
    
    Returns one of: GREETING, GATHERING, READY, FOLLOWUP
    """
    user_messages = [m for m in messages if m["role"] == "user"]
    has_symptoms = accumulated_symptoms.upper().strip() != "NONE" and len(accumulated_symptoms) > 2
    
    # If assessment was already given in this conversation
    if assessment_given:
        return "FOLLOWUP"
    
    # PRIORITY: If user said "no" / "nothing" and we have symptoms -> READY
    cleaned = user_input.strip().lower().rstrip("!?.,")
    if cleaned in ("no", "nope", "nothing", "nothing else", "that's it", "thats it",
                    "no more", "nah", "none", "not really", "no other", "no others"):
        if has_symptoms:
            return "READY"
    
    # If no symptoms at all and conversational -> GREETING
    if not has_symptoms and is_conversational(user_input):
        return "GREETING"
    
    # After 3+ user messages, we have enough info -> READY
    if len(user_messages) >= 3 and has_symptoms:
        return "READY"
    
    # If user has provided detailed symptoms (location + duration, or severity + any detail)
    sym = accumulated_symptoms.lower()
    detail_count = 0
    if any(loc in sym for loc in ["left", "right", "front", "back", "side", "temple", "forehead", "top"]):
        detail_count += 1
    if any(dur in sym for dur in ["day", "week", "hour", "month", "morning", "night"]):
        detail_count += 1
    if any(sev in sym for sev in ["severe", "mild", "moderate", "sharp", "dull", "throbbing", "intense"]):
        detail_count += 1
    if "," in sym or " and " in sym:
        detail_count += 1
    
    if detail_count >= 2:
        return "READY"
    
    # Still gathering (first turn with symptoms, need more info)
    return "GATHERING"


def extract_all_symptoms(messages):
    """Extract all symptoms mentioned throughout the conversation."""
    return extract_symptoms_from_history(messages)


def auto_save():
    """Auto-save the current conversation after every message exchange."""
    if "current_conv_id" in st.session_state and st.session_state.messages:
        save_messages(st.session_state.current_conv_id, st.session_state.messages)


def get_vision_models():
    """Check which vision models are available in Ollama."""
    import requests
    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        available = [m["name"] for m in resp.json().get("models", [])]
        return [m for m in available if any(v in m.lower() for v in ["llava", "vision", "bakllava", "svlm"])]
    except Exception:
        return []


def analyze_image_with_text(image_b64: str, user_text: str, chat_context: str) -> str:
    """
    Send an image + user text to the vision model for FIRST-TIME analysis.
    Only called once on upload.  Yields partial response for streaming.
    """
    vision_models = get_vision_models()
    if not vision_models:
        return None

    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage

    model_name = vision_models[0]
    logger.info(f"Vision analysis with model: {model_name}")
    llm = ChatOllama(model=model_name, temperature=0.2)

    prompt_text = (
        "You are SymptoGuide AI, a medical assistant. "
        "The user uploaded a medical image.\n\n"
        f"CONVERSATION CONTEXT:\n{chat_context}\n\n"
        f"USER'S QUESTION: {user_text}\n\n"
        "INSTRUCTIONS:\n"
        "- Analyze the image thoroughly\n"
        "- If it's a lab result: list each test, its value, the normal range, "
        "and whether it is NORMAL or ABNORMAL. Use a concise table/list format.\n"
        "- If it's a skin condition: describe appearance, possible conditions\n"
        "- If it's an X-ray/scan: describe visible structures and anomalies\n"
        "- At the END, add a section connecting findings to any symptoms "
        "the user mentioned (headache, fever, etc.)\n"
        "- Do NOT make definitive diagnoses\n"
        "- Recommend consulting a healthcare provider"
    )

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"},
        ]
    )

    full_response = ""
    for chunk in llm.stream([message]):
        full_response += chunk.content
        yield full_response


# Prompt for follow-up questions ABOUT a previously-analyzed image.
# Uses the TEXT model with the cached analysis — no re-sending the image.
IMAGE_FOLLOWUP_PROMPT = """You are SymptoGuide AI, a medical assistant.

The user previously uploaded a medical image (lab results / scan / photo).
Here is the ANALYSIS that was already performed on that image:

--- IMAGE ANALYSIS ---
{image_analysis}
--- END ANALYSIS ---

Recent conversation:
{recent_chat}

The user's new question: {input}

INSTRUCTIONS:
- Answer the question using the image analysis above as your source of truth.
- Do NOT repeat the full list of values. Only mention the RELEVANT tests/findings.
- If the user mentions symptoms (headache, fever, pain, etc.), explain which specific
  test results from the analysis are relevant to those symptoms and WHY.
- For example: if user has fever → check WBC, CRP, ESR. If headache → check
  hemoglobin, blood pressure, electrolytes.
- Be concise and focused. Give a direct answer.
- If no test results relate to the symptom, say so clearly.
- Always recommend seeing a healthcare provider for definitive interpretation.
"""

# ============================================================================
#  LOGGING SETUP
# ============================================================================

def setup_logging():
    """Initialize logging to file and console."""
    os.makedirs(MedicalConfig.LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(MedicalConfig.LOG_DIR, "session.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("SymptoGuide")


logger = setup_logging()

# ============================================================================
#  PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title=MedicalConfig.PAGE_TITLE,
    page_icon=MedicalConfig.PAGE_ICON,
    layout="wide"
)

# Dark theme styling
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .stChatMessage { background-color: #161B22; border: 1px solid #30363D; border-radius: 10px; }
    h1, h2, h3 { color: #58A6FF !important; }
    p, li { color: #C9D1D9 !important; }
    .emergency-alert {
        background-color: #381315; color: #FF7B72; padding: 15px;
        border-radius: 8px; border: 1px solid #FFA198; border-left: 5px solid #FF7B72;
        font-weight: bold; margin-bottom: 20px;
    }
    .router-box {
        background-color: #0D1117; color: #79C0FF; padding: 8px;
        border-radius: 6px; border: 1px solid #1F6FEB; font-family: monospace; font-size: 0.85rem;
    }
    .source-box {
        background-color: #161B22; color: #8B949E; padding: 10px;
        border-radius: 6px; border-left: 3px solid #238636; margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

st.title(f"{MedicalConfig.PAGE_ICON} {MedicalConfig.PAGE_TITLE}")
st.caption("Medical Assistant | Intent-Aware RAG System")

# ============================================================================
#  SIDEBAR — Multi-Chat + Photo Upload
# ============================================================================

# Default to local Ollama mode
set_mode("Local (Ollama)")
show_debug = False

# --- Initialise conversation state ---
if "current_conv_id" not in st.session_state:
    # Try to resume the most recent conversation
    all_convs = list_conversations()
    if all_convs:
        latest = load_conversation(all_convs[0]["id"])
        if latest:
            st.session_state.current_conv_id = latest["id"]
            st.session_state.messages = latest["messages"]
        else:
            new = create_conversation()
            st.session_state.current_conv_id = new["id"]
            st.session_state.messages = []
    else:
        new = create_conversation()
        st.session_state.current_conv_id = new["id"]
        st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_context" not in st.session_state:
    st.session_state["last_context"] = ""

if "active_image" not in st.session_state:
    st.session_state["active_image"] = None

if "image_analysis" not in st.session_state:
    st.session_state["image_analysis"] = None

if "assessment_given" not in st.session_state:
    st.session_state["assessment_given"] = False

# --- Sidebar layout ---
with st.sidebar:
    st.title("🩺 SymptoGuide")

    # ➕ New Chat button
    if st.button("➕  New Chat", use_container_width=True, type="primary"):
        # Save current conversation first
        auto_save()
        new = create_conversation()
        st.session_state.current_conv_id = new["id"]
        st.session_state.messages = []
        st.session_state["last_context"] = ""
        st.session_state["active_image"] = None
        st.session_state["image_analysis"] = None
        st.session_state["assessment_given"] = False
        st.rerun()

    st.divider()

    # 📎 File Upload (images + PDFs)
    st.markdown("**📎 Upload Medical File**")
    uploaded_file = st.file_uploader(
        "Upload a photo or PDF (lab result, report, skin photo, etc.)",
        type=["jpg", "jpeg", "png", "pdf"],
        label_visibility="collapsed",
        key="photo_upload",
    )

    st.divider()

    # 📜 Conversation History
    st.markdown("**💬 Chat History**")
    all_convs = list_conversations()
    for conv in all_convs[:20]:  # show last 20
        cols = st.columns([5, 1])
        is_active = conv["id"] == st.session_state.current_conv_id
        label = f"{'▸ ' if is_active else ''}{conv['title']}"
        with cols[0]:
            if st.button(label, key=f"conv_{conv['id']}", use_container_width=True,
                         disabled=is_active):
                auto_save()
                loaded = load_conversation(conv["id"])
                if loaded:
                    st.session_state.current_conv_id = loaded["id"]
                    st.session_state.messages = loaded["messages"]
                    st.session_state["last_context"] = ""
                    st.rerun()
        with cols[1]:
            if st.button("🗑️", key=f"del_{conv['id']}"):
                delete_conversation(conv["id"])
                if conv["id"] == st.session_state.current_conv_id:
                    new = create_conversation()
                    st.session_state.current_conv_id = new["id"]
                    st.session_state.messages = []
                st.rerun()

# ============================================================================
# 📦 LOAD RESOURCES
# ============================================================================

try:
    vector_db = load_vector_db()
except Exception as e:
    st.error(f"Error loading resources: {e}")
    logger.error(f"Resource loading failed: {e}")
    st.stop()

# ============================================================================
#  CHAT INTERFACE
# ============================================================================

# Display message history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("image"):
            st.image(base64.b64decode(msg["image"]), caption="Uploaded image")
        st.markdown(msg["content"], unsafe_allow_html=True)

# Chat input
user_input = st.chat_input("Describe your symptoms or ask a question...")

if user_input:
    # Validate and clean input
    user_input = user_input.strip()
    if not user_input:
        st.warning("Please enter something.")
        st.stop()
    
    # Limit input length
    if len(user_input) > 500:
        st.warning("Input too long. Please use fewer than 500 characters.")
        st.stop()
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    auto_save()
    with st.chat_message("user"):
        st.markdown(user_input)
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        retrieved_docs = []  # for references
        
        try:
            # --- STEP 0: IMAGE-CONTEXT CHECK ---
            # If there's a cached image analysis, use the TEXT model for
            # follow-up questions (no re-sending the image to the vision model).
            has_image_analysis = st.session_state.get("image_analysis") is not None
            
            if has_image_analysis:
                # Use the fast TEXT model with the cached analysis
                recent_chat = format_chat_context(st.session_state.messages[:-1])
                with st.spinner("🩺 Connecting your symptoms to the image..."):
                    try:
                        followup_chain = build_chain(IMAGE_FOLLOWUP_PROMPT, temperature=0.2)
                        for chunk in followup_chain.stream({
                            "input": user_input,
                            "image_analysis": st.session_state["image_analysis"],
                            "recent_chat": recent_chat,
                        }):
                            full_response += chunk
                            message_placeholder.markdown(full_response + "▌")
                        message_placeholder.markdown(full_response)
                    except Exception as e:
                        logger.error(f"Image follow-up failed: {e}")
                        full_response = None
                
                if full_response:
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    auto_save()
                    st.stop()
                else:
                    full_response = ""
            
            # --- STEP 1: EMERGENCY CHECK ---
            emergency_alert = fast_emergency_check(user_input)
            if emergency_alert:
                full_response = f"""
                <div class='emergency-alert'>
                    🚨 <b>EMERGENCY DETECTED: {emergency_alert}</b><br>
                    Please call 999 or go to the nearest Emergency Room immediately.<br>
                    Do not wait for an AI response.
                </div>
                """
                message_placeholder.markdown(full_response, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": "🚨 EMERGENCY ALERT TRIGGERED"})
                auto_save()
                logger.critical(f"Emergency Triggered: {user_input}")
                st.stop()
            
            # --- STEP 1B: CROSS-TURN COMPOUND EMERGENCY CHECK ---
            compound_alert = check_compound_emergency(st.session_state.messages)
            if compound_alert:
                full_response = compound_alert["call_to_action"]
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                auto_save()
                logger.critical(f"Compound Emergency: {compound_alert['name']} ({compound_alert['matched_groups']}/{compound_alert['total_groups']} groups)")
                st.stop()
            
            # --- STEP 2: SMART ROUTING → STAGE DETECTION → RESPOND ---
            context_text = ""
            accumulated_symptoms = "NONE"
            has_symptoms = False
            
            with st.spinner("🩺 Thinking..."):
                # 2a. Determine if this is a conversational or medical message
                conversational = is_conversational(user_input)
                
                # 2b. Accumulate symptoms (skip for purely conversational messages
                # when no symptoms have been discussed yet)
                if not conversational or len(st.session_state.messages) > 2:
                    chat_history = format_chat_context(st.session_state.messages)
                    try:
                        accum_chain = build_chain(SYMPTOM_ACCUMULATION_PROMPT, temperature=0.0)
                        accumulated_symptoms = ""
                        for chunk in accum_chain.stream({"input": user_input, "chat_history": chat_history}):
                            accumulated_symptoms += chunk
                        accumulated_symptoms = accumulated_symptoms.strip()
                    except Exception as e:
                        logger.warning(f"Symptom accumulation failed: {e}")
                        accumulated_symptoms = "NONE"
                
                has_symptoms = accumulated_symptoms.upper().strip() != "NONE" and len(accumulated_symptoms) > 2
                
                # 2c. Determine conversation stage
                stage = determine_stage(
                    st.session_state.messages, user_input,
                    accumulated_symptoms, st.session_state.get("assessment_given", False)
                )
                
                if show_debug:
                    st.markdown(
                        f"<div class='router-box'>🎯 <b>Stage:</b> {stage} | 🔑 <b>Symptoms:</b> {accumulated_symptoms}</div>",
                        unsafe_allow_html=True
                    )
                
                # 2d. RAG search — only when stage is READY or GATHERING with symptoms
                if has_symptoms and stage in ("READY", "GATHERING", "FOLLOWUP"):
                    try:
                        retrieved_with_scores = smart_category_search(vector_db, accumulated_symptoms)
                    except Exception as e:
                        logger.error(f"Vector search failed: {e}")
                        retrieved_with_scores = []
                    
                    if retrieved_with_scores:
                        docs, scores = zip(*retrieved_with_scores)
                        retrieved_docs = list(docs)
                        for doc in docs:
                            category = doc.metadata.get('entity_type', 'General').upper()
                            name = doc.metadata.get('name', 'Unknown')
                            context_text += f"--- {category}: {name} ---\n{doc.page_content}\n\n"
                
                # 2e. Generate response with build_chat_chain (System + Human separation)
                recent_chat = format_chat_context(st.session_state.messages[:-1])
                
                # Map stage label to full instruction text
                stage_instructions = {
                    "GREETING": STAGE_GREETING,
                    "GATHERING": STAGE_GATHERING,
                    "READY": STAGE_READY,
                    "FOLLOWUP": STAGE_FOLLOWUP,
                }
                stage_text = stage_instructions.get(stage, STAGE_GATHERING)
                
                try:
                    response_chain = build_chat_chain(SYSTEM_IDENTITY, HUMAN_TEMPLATE, temperature=0.3)
                    for chunk in response_chain.stream({
                        "input": user_input,
                        "context": context_text if context_text else "(No medical evidence retrieved.)",
                        "recent_chat": recent_chat if recent_chat else "(Start of conversation.)",
                        "symptoms_so_far": accumulated_symptoms if has_symptoms else "(No symptoms reported yet.)",
                        "stage": stage_text,
                    }):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                    
                    # Track if we gave an assessment
                    if stage == "READY":
                        st.session_state["assessment_given"] = True
                        
                except Exception as e:
                    logger.error(f"Response generation failed: {e}")
                    full_response = "I encountered an error generating a response. Please try again or rephrase your question."
                    message_placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"System error: {str(e)[:100]}. Please try again."
            st.error(full_response)
            logger.error(f"Unexpected error: {e}", exc_info=True)
        
        # Save message and persist chat (auto-save)
        if full_response:
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            auto_save()
        
        # --- 📚 REFERENCES ---
        if retrieved_docs:
            seen_refs = set()
            ref_items = []
            for doc in retrieved_docs:
                name = doc.metadata.get('name', '')
                url = doc.metadata.get('url', '')
                source = doc.metadata.get('source', '')
                ref_key = name or url
                if ref_key and ref_key not in seen_refs:
                    seen_refs.add(ref_key)
                    if url:
                        ref_items.append(f"- [{name}]({url}) — *{source}*" if source else f"- [{name}]({url})")
                    elif name:
                        ref_items.append(f"- **{name}** — *{source}*" if source else f"- **{name}**")
            
            if ref_items:
                with st.expander("📚 Medical References", expanded=False):
                    st.markdown("\n".join(ref_items))

# ============================================================================
#  FILE UPLOAD HANDLER (Images + PDFs)
# ============================================================================

if uploaded_file is not None and "last_uploaded_file" not in st.session_state:
    st.session_state["last_uploaded_file"] = uploaded_file.name
    file_bytes = uploaded_file.read()
    file_ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    is_pdf = file_ext == "pdf"

    # --- PDF HANDLING ---
    if is_pdf:
        user_msg = {
            "role": "user",
            "content": f"📄 *Uploaded PDF: {uploaded_file.name}*\n\nPlease analyze this medical document.",
        }
        st.session_state.messages.append(user_msg)

        with st.chat_message("user"):
            st.markdown(f"📄 *Uploaded PDF: {uploaded_file.name}*")

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            try:
                import io
                try:
                    from PyPDF2 import PdfReader
                except ImportError:
                    from pypdf import PdfReader  # fallback

                reader = PdfReader(io.BytesIO(file_bytes))
                pdf_text = ""
                for page in reader.pages:
                    pdf_text += page.extract_text() or ""

                if not pdf_text.strip():
                    full_response = (
                        "📄 **PDF received**, but I couldn't extract any text from it. "
                        "It may be a scanned document or image-based PDF.\n\n"
                        "Please take a screenshot of the relevant page and upload it as an image, "
                        "or type out the key values and I'll help interpret them."
                    )
                    message_placeholder.markdown(full_response)
                else:
                    # Truncate very long PDFs
                    if len(pdf_text) > 4000:
                        pdf_text = pdf_text[:4000] + "\n\n[... document truncated ...]"

                    # Use the text LLM to analyze
                    pdf_prompt = (
                        "You are SymptoGuide AI, a medical assistant. "
                        "The user uploaded a medical PDF document. Below is the extracted text. "
                        "Analyze the document and provide a clear, helpful summary.\n"
                        "- Highlight any abnormal values or concerning findings\n"
                        "- Explain medical terms in plain language\n"
                        "- Recommend next steps if appropriate\n"
                        "- Always recommend consulting a healthcare provider for a definitive interpretation\n\n"
                        f"--- DOCUMENT TEXT ---\n{pdf_text}\n--- END ---"
                    )

                    diagnosis_chain = build_chain(DIAGNOSIS_PROMPT, temperature=0.2)
                    full_response = ""
                    with st.spinner("📄 Analyzing document..."):
                        for chunk in diagnosis_chain.stream({"input": pdf_prompt, "context": pdf_text, "recent_chat": ""}):
                            full_response += chunk
                            message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)

            except Exception as e:
                logger.error(f"PDF analysis failed: {e}")
                full_response = (
                    "📄 **PDF received!** Unfortunately, I encountered an error reading the document.\n\n"
                    "Please copy and paste the key information and I'll help you interpret it."
                )
                message_placeholder.markdown(full_response)

            st.session_state.messages.append({"role": "assistant", "content": full_response})
            auto_save()

    # --- IMAGE HANDLING ---
    else:
        image_b64 = base64.b64encode(file_bytes).decode("utf-8")

        # Store image in session for follow-up text questions
        st.session_state["active_image"] = image_b64

        user_msg = {
            "role": "user",
            "content": f"📸 *Uploaded image: {uploaded_file.name}*\n\nPlease analyze this medical image.",
            "image": image_b64,
        }
        st.session_state.messages.append(user_msg)

        with st.chat_message("user"):
            st.image(file_bytes, caption=uploaded_file.name)
            st.markdown(f"📸 *Uploaded: {uploaded_file.name}*")

        # Analyze with vision model using chat context
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            chat_context = format_chat_context(st.session_state.messages[:-1])

            try:
                full_response = ""
                with st.spinner("🔬 Analyzing image..."):
                    for partial in analyze_image_with_text(
                        image_b64,
                        "Please analyze this uploaded medical image.",
                        chat_context,
                    ):
                        full_response = partial
                        message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)

                if not full_response:
                    raise ValueError("No vision model available")

                # Cache the analysis so follow-up questions use the TEXT model
                st.session_state["image_analysis"] = full_response

            except Exception as e:
                logger.warning(f"Vision analysis: {e}")
                vision_models = get_vision_models()
                if not vision_models:
                    full_response = (
                        "📸 **Image received!** I can see your upload, but I don't currently have a vision model "
                        "installed to analyze images.\n\n"
                        "**To enable image analysis**, install a vision model with:\n"
                        "```\nollama pull llava\n```\n\n"
                        "In the meantime, please describe what the image shows (e.g., lab values, skin appearance) "
                        "and I'll help you interpret it."
                    )
                else:
                    full_response = (
                        "📸 **Image received!** Unfortunately, I encountered an error analyzing the image.\n\n"
                        "You can still ask me questions about it by typing below — I'll use the image as context."
                    )
                message_placeholder.markdown(full_response)

            st.session_state.messages.append({"role": "assistant", "content": full_response})
            auto_save()

elif uploaded_file is None and "last_uploaded_file" in st.session_state:
    del st.session_state["last_uploaded_file"]
