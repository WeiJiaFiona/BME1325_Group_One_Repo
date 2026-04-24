from __future__ import annotations

import json
import os
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None


def _extract_first_json_object(text: str) -> Dict[str, object]:
    """
    Tolerant loader: some course configs include a JSON object followed by human notes.
    We only consume the first JSON object and ignore trailing text.
    """
    raw = (text or "").strip()
    if not raw:
        return {}
    # Fast path: pure JSON.
    if raw.startswith("{") and raw.rstrip().endswith("}"):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
    # Fallback: extract first top-level JSON object with brace matching.
    start = raw.find("{")
    if start < 0:
        return {}
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i, ch in enumerate(raw[start:], start=start):
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        return {}
    snippet = raw[start : end + 1]
    try:
        obj = json.loads(snippet)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _load_repo_openai_config() -> Dict[str, str]:
    # Prefer local config in this runnable tree, but also support the course-level
    # config file at week6/week6/openai_config.json.
    here = Path(__file__).resolve()
    candidates = [
        # user_mode/openai_config.json
        here.parents[2] / "openai_config.json",
        # repo/week6/week6/openai_config.json (common for submissions)
        here.parents[3] / "openai_config.json",
    ]
    best: Dict[str, str] = {}
    for p in candidates:
        if not p.exists():
            continue
        try:
            data = _extract_first_json_object(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        api_key = str(data.get("model-key", "")).strip()
        model = str(data.get("model", "")).strip()
        endpoint = str(data.get("model-endpoint", "")).strip()
        # Prefer configs that actually include a key.
        if api_key:
            return {"api_key": api_key, "model": model, "endpoint": endpoint}
        if not best:
            best = {"api_key": api_key, "model": model, "endpoint": endpoint}
    return best


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

    def _read_response(resp_body: Dict[str, object]) -> Optional[str]:
        if endpoint.lower().endswith("/api/v1/start"):
            if resp_body.get("success") is False:
                return None
            choices = resp_body.get("choices") or []
            if choices:
                msg = choices[0].get("message", {}).get("content", "")
                if isinstance(msg, list):
                    text_parts = [p.get("text", "") for p in msg if isinstance(p, dict) and p.get("type") == "text"]
                    out = "\n".join([p for p in text_parts if p]).strip()
                    return out or None
                return str(msg).strip() or None
            return None
        choices = resp_body.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        return str(content).strip() or None

    # Try normal transport first. If proxy chain is broken (common in this env), retry with proxy disabled.
    transport_errors = (urllib.error.URLError, ssl.SSLError, ConnectionError, TimeoutError, OSError)

    def _do_request(disable_proxy: bool = False) -> Optional[str]:
        context = ssl.create_default_context()
        if disable_proxy:
            if requests is not None:
                s = requests.Session()
                s.trust_env = False
                r = s.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    json=payload,
                    timeout=12,
                )
                r.raise_for_status()
                body = r.json()
            else:
                proxy_keys = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]
                backup = {k: os.environ.get(k) for k in proxy_keys}
                try:
                    for k in proxy_keys:
                        os.environ.pop(k, None)
                    with urllib.request.urlopen(req, timeout=12, context=context) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                finally:
                    for k, v in backup.items():
                        if v is not None:
                            os.environ[k] = v
        else:
            with urllib.request.urlopen(req, timeout=12, context=context) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        return _read_response(body)

    try:
        return _do_request(disable_proxy=False)
    except transport_errors:
        try:
            return _do_request(disable_proxy=True)
        except Exception:
            return None
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


def generate_from_prompt(prompt: str, fallback: str) -> str:
    """
    Use raw prompt text (already includes any evidence/context).
    This is used by doctor_kb RAG to inject evidence snippets while keeping hard-rule boundaries elsewhere.
    """
    out = _chat_completion(prompt)
    return out if out else fallback
