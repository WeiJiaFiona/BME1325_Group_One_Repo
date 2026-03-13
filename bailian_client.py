import json
import os
import socket
from pathlib import Path
from typing import Any
from urllib import error, request

DASHSCOPE_API_ENV = "DASHSCOPE_API_KEY"
DEFAULT_BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_BAILIAN_CHAT_MODEL = "qwen3.5-plus"
DEFAULT_BAILIAN_STRUCTURED_MODEL = "qwen-plus"
DEFAULT_TIMEOUT_SECONDS = 30


class BailianAPIError(RuntimeError):
    """Raised when the Bailian API request fails."""


class BailianConfigError(BailianAPIError):
    """Raised when the local Bailian configuration is missing or invalid."""


def _load_local_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env_file()


def is_bailian_configured() -> bool:
    return bool(os.getenv(DASHSCOPE_API_ENV))


def get_bailian_api_key() -> str:
    api_key = os.getenv(DASHSCOPE_API_ENV)
    if not api_key:
        raise BailianConfigError(
            "未检测到环境变量 DASHSCOPE_API_KEY。请先在系统环境变量、当前终端，或项目根目录的 .env 文件中配置百炼 API Key。"
        )
    return api_key


def get_bailian_base_url() -> str:
    return os.getenv("BAILIAN_BASE_URL", DEFAULT_BAILIAN_BASE_URL).rstrip("/")


def get_bailian_chat_model() -> str:
    return os.getenv("BAILIAN_MODEL", DEFAULT_BAILIAN_CHAT_MODEL)


def get_bailian_structured_model() -> str:
    return os.getenv("BAILIAN_STRUCTURED_MODEL", DEFAULT_BAILIAN_STRUCTURED_MODEL)


def _build_chat_completions_url() -> str:
    return f"{get_bailian_base_url()}/chat/completions"


def _extract_text_content(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif item.get("type") == "output_text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
        return "".join(text_parts)

    return str(content)


def chat_completions(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model or get_bailian_chat_model(),
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {get_bailian_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = request.Request(
        _build_chat_completions_url(),
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except (TimeoutError, socket.timeout) as exc:
        raise BailianAPIError("百炼 API 请求超时，请稍后重试。") from exc
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise BailianAPIError(f"百炼 API 调用失败：HTTP {exc.code}，响应：{detail}") from exc
    except error.URLError as exc:
        raise BailianAPIError(f"百炼 API 网络错误：{exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise BailianAPIError("百炼 API 返回了无法解析的 JSON。") from exc


def query_bailian(
    query: str,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": query})

    raw_response = chat_completions(
        messages=messages,
        model=model,
        temperature=temperature,
        response_format=response_format,
    )

    return {
        "provider": "阿里云百炼",
        "model": raw_response.get("model") or model or get_bailian_chat_model(),
        "content": _extract_text_content(raw_response),
        "usage": raw_response.get("usage"),
        "request_id": raw_response.get("id"),
        "raw_response": raw_response,
    }


def _build_triage_extraction_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "triage_incremental_update",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "当前患者这轮消息中明确提到的症状，使用中文短语。",
                    },
                    "associated_symptoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本轮明确提到的伴随症状，使用中文短语。",
                    },
                    "onset_time": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "起病时间，例如昨天、今天早上。",
                    },
                    "duration": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "持续时间，例如2天、3小时。",
                    },
                    "severity": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "严重程度，例如轻度、中度、重度。",
                    },
                    "trauma_history": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "本轮是否明确说明有外伤史。",
                    },
                    "temperature": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "description": "体温，摄氏度。",
                    },
                    "temperature_status": {
                        "anyOf": [
                            {"type": "string", "enum": ["已知", "缺失", "未知"]},
                            {"type": "null"},
                        ],
                        "description": "体温状态，只能是已知、缺失、未知或 null。",
                    },
                    "pain_score": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "疼痛评分，0 到 10。",
                    },
                    "suspected_risk_signals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "疑似风险信号，例如疑似隐匿性出血、休克风险。",
                    },
                },
                "required": [
                    "symptoms",
                    "associated_symptoms",
                    "onset_time",
                    "duration",
                    "severity",
                    "trauma_history",
                    "temperature",
                    "temperature_status",
                    "pain_score",
                    "suspected_risk_signals",
                ],
                "additionalProperties": False,
            },
        },
    }


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                normalized.append(text)
    return sorted(set(normalized))


def _normalize_extraction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    symptoms = _normalize_string_list(payload.get("symptoms"))
    if symptoms:
        updates["symptoms"] = symptoms

    associated_symptoms = _normalize_string_list(payload.get("associated_symptoms"))
    if associated_symptoms:
        updates["associated_symptoms"] = associated_symptoms

    suspected_risk_signals = _normalize_string_list(payload.get("suspected_risk_signals"))
    if suspected_risk_signals:
        updates["suspected_risk_signals"] = suspected_risk_signals

    for field_name in ["onset_time", "duration", "severity"]:
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            updates[field_name] = value.strip()

    trauma_history = payload.get("trauma_history")
    if isinstance(trauma_history, bool):
        updates["trauma_history"] = trauma_history

    temperature = payload.get("temperature")
    if isinstance(temperature, (int, float)) and 30 <= float(temperature) <= 45:
        updates["temperature"] = float(temperature)

    temperature_status = payload.get("temperature_status")
    if temperature_status in {"已知", "缺失", "未知"}:
        updates["temperature_status"] = temperature_status

    pain_score = payload.get("pain_score")
    if isinstance(pain_score, int) and 0 <= pain_score <= 10:
        updates["pain_score"] = pain_score

    return updates


def extract_triage_updates(message: str, session_snapshot: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "你是医院分诊系统的信息抽取器，只负责从患者本轮最新一句话中抽取结构化信息，"
        "不做疾病诊断，不补充患者没有说过的事实。"
        "输出必须严格符合指定 JSON Schema。"
        "若本轮消息没有提到某个字段，则返回 null 或空数组。"
        "症状、伴随症状、风险信号统一使用中文短语。"
    )
    user_prompt = (
        "请基于以下当前会话上下文和患者本轮新消息，提取本轮新增或修正的信息。\n\n"
        f"当前会话上下文：{json.dumps(session_snapshot, ensure_ascii=False)}\n"
        f"患者本轮新消息：{message}"
    )

    result = query_bailian(
        query=user_prompt,
        system_prompt=system_prompt,
        model=get_bailian_structured_model(),
        temperature=0.0,
        response_format=_build_triage_extraction_schema(),
    )

    try:
        payload = json.loads(result["content"])
    except json.JSONDecodeError as exc:
        raise BailianAPIError("百炼结构化提取返回的内容不是合法 JSON。") from exc

    return _normalize_extraction_payload(payload)
