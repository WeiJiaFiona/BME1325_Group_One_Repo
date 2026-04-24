"""
Multi-conversation chat manager for SymptoGuide AI.

Manages multiple chat sessions stored as individual JSON files in
``logs/conversations/``.  Each conversation is identified by a UUID and
stores messages + metadata (title, created/updated timestamps).
"""

import json
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from src.app.config import MedicalConfig

logger = logging.getLogger("SymptoGuide")

CONVERSATIONS_DIR = Path(MedicalConfig.LOG_DIR) / "conversations"
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
#  CONVERSATION I/O
# ============================================================================

def _conversation_path(conv_id: str) -> Path:
    return CONVERSATIONS_DIR / f"{conv_id}.json"


def create_conversation() -> Dict:
    """Create a new conversation and return its metadata dict."""
    conv_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "id": conv_id,
        "title": "New Chat",
        "created": now,
        "updated": now,
        "messages": [],
    }
    _save_conversation(data)
    logger.info(f"Created conversation: {conv_id}")
    return data


def _save_conversation(data: Dict) -> None:
    """Write conversation data to disk."""
    try:
        path = _conversation_path(data["id"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save conversation {data.get('id')}: {e}")


def load_conversation(conv_id: str) -> Optional[Dict]:
    """Load a conversation by ID.  Returns None if not found."""
    path = _conversation_path(conv_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load conversation {conv_id}: {e}")
        return None


def save_messages(conv_id: str, messages: List[Dict]) -> None:
    """
    Persist the message list for a conversation and auto-generate a title
    from the first user message if the title is still 'New Chat'.
    """
    data = load_conversation(conv_id)
    if data is None:
        data = {
            "id": conv_id,
            "title": "New Chat",
            "created": datetime.now().isoformat(timespec="seconds"),
            "updated": datetime.now().isoformat(timespec="seconds"),
            "messages": messages,
        }
    else:
        data["messages"] = messages
        data["updated"] = datetime.now().isoformat(timespec="seconds")

    # Auto-title: use the first user message (truncated)
    if data["title"] == "New Chat":
        for msg in messages:
            if msg.get("role") == "user":
                text = msg["content"][:40].strip()
                if text:
                    data["title"] = text + ("…" if len(msg["content"]) > 40 else "")
                break

    _save_conversation(data)


def delete_conversation(conv_id: str) -> None:
    """Delete a conversation file."""
    path = _conversation_path(conv_id)
    if path.exists():
        path.unlink()
        logger.info(f"Deleted conversation: {conv_id}")


def list_conversations() -> List[Dict]:
    """
    Return a list of conversation summaries sorted by last-updated (newest first).
    Each item has: id, title, updated, message_count.
    """
    conversations = []
    for path in CONVERSATIONS_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            conversations.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "updated": data.get("updated", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue

    conversations.sort(key=lambda c: c["updated"], reverse=True)
    return conversations
