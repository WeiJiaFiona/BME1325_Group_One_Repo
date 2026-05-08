from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Dict, Optional


def _load_repo_openai_config() -> Dict[str, str]:
    cfg_path = Path(__file__).resolve().parents[2] / "openai_config.json"
    if not cfg_path.exists():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "api_key": str(data.get("model-key", "")).strip(),
        "model": str(data.get("model", "")).strip(),
        "endpoint": str(data.get("model-endpoint", "")).strip(),
    }


def _resolve_llm_config() -> Dict[str, str]:
    cfg = _load_repo_openai_config()
    api_key = (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("OPENAI_KEY", "").strip()
        or cfg.get("api_key", "")
    )
    model = os.getenv("OPENAI_MODEL", "").strip() or cfg.get("model", "") or "gpt-4o-mini"
    endpoint = (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("OPENAI_ENDPOINT", "").strip()
        or cfg.get("endpoint", "")
        or "https://api.openai.com/v1"
    )
    return {"api_key": api_key, "model": model, "endpoint": endpoint.rstrip("/")}


def llm_enabled() -> bool:
    # Default ON for this project; explicitly set ENABLE_LLM_AGENTS=0 to disable.
    if os.getenv("ENABLE_LLM_AGENTS", "1").strip() in {"0", "false", "False", "no", "NO"}:
        return False
    return bool(_resolve_llm_config()["api_key"])


def _chat_completion(prompt: str, *, max_tokens: int = 180) -> Optional[str]:
    if not llm_enabled():
        return None

    cfg = _resolve_llm_config()
    api_key = cfg["api_key"]
    endpoint = cfg["endpoint"]
    model = cfg["model"]

    # Support OpenAI-compatible /api/v1/start endpoints and standard chat/completions.
    if endpoint.lower().endswith("/api/v1/start"):
        url = endpoint
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
            "temperature": 0.2,
            "n": 1,
            "stream": False,
            "max_completion_tokens": max_tokens,
        }
    else:
        url = f"{endpoint}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an emergency department clinician assistant. Keep responses concise and safe."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if endpoint.lower().endswith("/api/v1/start"):
                # Provider-specific error envelope.
                if body.get("success") is False:
                    return None
                choices = body.get("choices") or []
                if choices:
                    msg = choices[0].get("message", {}).get("content", "")
                    if isinstance(msg, list):
                        text_parts = [p.get("text", "") for p in msg if isinstance(p, dict) and p.get("type") == "text"]
                        out = "\n".join([p for p in text_parts if p]).strip()
                        return out or None
                    return str(msg).strip() or None
                return None
            choices = body.get("choices") or []
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content", "")
            return str(content).strip() or None
    except Exception:
        return None


def generate_clinical_reply(agent: str, context: Dict[str, object], fallback: str) -> str:
    prompt = (
        f"Agent: {agent}\n"
        f"Context JSON: {json.dumps(context, ensure_ascii=True)}\n"
        "Write one natural sentence to the patient. "
        "Do not invent actions that conflict with the context."
    )
    out = _chat_completion(prompt)
    return out if out else fallback
