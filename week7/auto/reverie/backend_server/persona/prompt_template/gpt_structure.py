import os
import time
import json
import hashlib
import queue
import socket
import subprocess
import threading
from collections import OrderedDict
from typing import Optional
from urllib.parse import urlparse
from pathlib import Path
from openai import AzureOpenAI, OpenAI

from utils import *
from openai_cost_logger import DEFAULT_LOG_PATH
from persona.prompt_template.openai_logger_singleton import OpenAICostLogger_Singleton


# ---------------------------------------------------------------------------
# Retry helper for transient OpenAI errors (500, 502, 503, 429, etc.)
# Uses exponential backoff: 60s -> 120s -> 300s (1 min, 2 min, 5 min)
# ---------------------------------------------------------------------------
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
_RETRY_DELAYS = [60, 120, 300]  # seconds
_LOCAL_EMBED_DIM = int(os.environ.get("LOCAL_EMBEDDING_DIM", "1536"))
_START_TIMEOUT_SECONDS = max(1, int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30")))
_EMBEDDING_TIMEOUT_SECONDS = max(
  0.25,
  float(os.environ.get("EMBEDDING_TIMEOUT_SECONDS", os.environ.get("EMBEDDINGS_TIMEOUT_SECONDS", "2.0"))),
)
_EMBEDDING_RETRY_DELAYS = [
  float(chunk.strip()) for chunk in os.environ.get("EMBEDDING_RETRY_DELAYS", "1,3").split(",")
  if chunk.strip()
]
_EMBEDDING_NETWORK_PREFLIGHT_ENABLED = os.environ.get(
  "EMBEDDING_NETWORK_PREFLIGHT", "1"
).lower() not in ("0", "false", "no")
_EMBEDDING_PREFLIGHT_TIMEOUT_SECONDS = max(
  0.1,
  float(os.environ.get("EMBEDDING_PREFLIGHT_TIMEOUT_SECONDS", "0.75")),
)


def _is_retryable(exc):
    """Return True if the exception looks like a transient OpenAI error."""
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status and int(status) in _RETRYABLE_STATUS_CODES:
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("server_error", "rate limit", "overloaded", "502", "503"))


def _load_config_file() -> dict:
    if CONFIG_PATH.exists():
      with open(CONFIG_PATH, "r") as f:
        return json.load(f)
    return {}


def _config_from_env(base_config: Optional[dict] = None) -> dict:
    """Build openai_config from environment variables, falling back to file config."""
    base_config = base_config or {}
    return {
        "client":               os.environ.get("OPENAI_CLIENT", base_config.get("client", "openai")),
        "model":                os.environ.get("OPENAI_MODEL", base_config.get("model", "")),
        "model-key":            os.environ.get("OPENAI_KEY", base_config.get("model-key", "")),
        "model-endpoint":       os.environ.get("OPENAI_ENDPOINT", base_config.get("model-endpoint", "")),
        "model-api-version":    os.environ.get("OPENAI_API_VERSION", ""),
        "model-costs": {
            "input":  float(os.environ.get("OPENAI_MODEL_COST_INPUT", base_config.get("model-costs", {}).get("input", "0.0"))),
            "output": float(os.environ.get("OPENAI_MODEL_COST_OUTPUT", base_config.get("model-costs", {}).get("output", "0.0"))),
        },
        "embeddings-client":     os.environ.get("EMBEDDINGS_CLIENT", base_config.get("embeddings-client", "openai")),
        "embeddings":            os.environ.get("EMBEDDINGS_MODEL", base_config.get("embeddings", "")),
        "embeddings-key":        os.environ.get("EMBEDDINGS_KEY", base_config.get("embeddings-key", "")),
        "embeddings-endpoint":   os.environ.get("EMBEDDINGS_ENDPOINT", base_config.get("embeddings-endpoint", "")),
        "embeddings-api-version": os.environ.get("EMBEDDINGS_API_VERSION", ""),
        "embeddings-costs": {
            "input":  float(os.environ.get("EMBEDDINGS_COST_INPUT", base_config.get("embeddings-costs", {}).get("input", "0.0"))),
            "output": float(os.environ.get("EMBEDDINGS_COST_OUTPUT", base_config.get("embeddings-costs", {}).get("output", "0.0"))),
        },
        "experiment-name": os.environ.get("EXPERIMENT_NAME", base_config.get("experiment-name", "edsim")),
        "cost-upperbound": float(os.environ.get("COST_UPPERBOUND", base_config.get("cost-upperbound", "100.0"))),
    }


CONFIG_PATH = Path(__file__).resolve().parents[4] / 'openai_config.json'
_FILE_CONFIG = _load_config_file()

if any(os.environ.get(var) for var in (
    "OPENAI_KEY", "OPENAI_CLIENT", "OPENAI_MODEL", "OPENAI_ENDPOINT",
    "EMBEDDINGS_CLIENT", "EMBEDDINGS_MODEL", "EMBEDDINGS_KEY", "EMBEDDINGS_ENDPOINT",
)):
    openai_config = _config_from_env(_FILE_CONFIG)
elif _FILE_CONFIG:
    openai_config = _FILE_CONFIG
else:
    raise RuntimeError(
        "No OpenAI credentials found. "
        "Set OPENAI_KEY (and related env vars) or create openai_config.json."
    )

def setup_client(type: str, config: dict):
  """Setup the OpenAI client.

  Args:
      type (str): the type of client. Either "azure" or "openai".
      config (dict): the configuration for the client.

  Raises:
      ValueError: if the client is invalid.

  Returns:
      The client object created, either AzureOpenAI or OpenAI.
  """
  if type == "azure":
    kwargs = {
        "azure_endpoint": config["endpoint"],
        "api_key": config["key"],
        "api_version": config["api-version"],
    }
    if config.get("timeout") is not None:
      kwargs["timeout"] = config["timeout"]
    client = AzureOpenAI(**kwargs)
  elif type == "openai":
    kwargs = {"api_key": config["key"]}
    # Support OpenAI-compatible providers via custom base URL.
    if config.get("endpoint"):
      kwargs["base_url"] = config["endpoint"]
    if config.get("timeout") is not None:
      kwargs["timeout"] = config["timeout"]
    client = OpenAI(**kwargs)
  else:
    raise ValueError("Invalid client")
  return client


def _looks_like_start_endpoint(url: str) -> bool:
  if not url:
    return False
  normalized = url.strip().rstrip("/").lower()
  return normalized.endswith("/api/v1/start")


def _build_start_api_url(url: str) -> str:
  normalized = (url or "").strip().rstrip("/")
  if not normalized:
    return normalized
  if normalized.lower().endswith("/api/v1/start"):
    return normalized
  return f"{normalized}/start"


_MODEL_ENDPOINT = openai_config.get("model-endpoint", "")
_EMBEDDINGS_ENDPOINT = openai_config.get("embeddings-endpoint", "")
_USE_START_ENDPOINT = _looks_like_start_endpoint(_MODEL_ENDPOINT)
_FORCE_LOCAL_LLM = os.environ.get("USE_LOCAL_LLM", "").lower() in ("1", "true", "yes")
_LLM_MODE = os.environ.get("LLM_MODE", "remote_only").strip().lower() or "remote_only"
if _FORCE_LOCAL_LLM:
  _LLM_MODE = "local_only"
_FORCE_LOCAL_EMBEDDINGS = os.environ.get("USE_LOCAL_EMBEDDINGS", "").lower() in ("1", "true", "yes")
_EMBEDDING_MODE = os.environ.get("EMBEDDING_MODE", "hybrid").strip().lower() or "hybrid"
if _FORCE_LOCAL_EMBEDDINGS:
  _EMBEDDING_MODE = "local_only"
_EMBEDDING_CACHE_ENABLED = os.environ.get("EMBEDDING_CACHE_ENABLED", "1").lower() not in ("0", "false", "no")
_EMBEDDING_CACHE_MAX_ENTRIES = max(1, int(os.environ.get("EMBEDDING_CACHE_MAX_ENTRIES", "4096")))
_EMBEDDING_REMOTE_FAILURE_THRESHOLD = max(1, int(os.environ.get("EMBEDDING_REMOTE_FAILURE_THRESHOLD", "1")))
_EMBEDDING_REMOTE_COOLDOWN_SECONDS = max(0, int(float(os.environ.get("EMBEDDING_REMOTE_COOLDOWN_MINUTES", "5")) * 60))
_embedding_cache = OrderedDict()
_embedding_health = {
  "consecutive_failures": 0,
  "last_failure_at": None,
  "cooldown_until": 0.0,
}


def _llm_extra(prompt: str, **extra):
  payload = {
    "prompt_chars": len(prompt or ""),
    "provider": openai_config.get("client"),
    "start_endpoint": _USE_START_ENDPOINT,
  }
  payload.update(extra)
  return payload


def _normalize_embedding_text(text: str) -> str:
  normalized = " ".join((text or "").replace("\n", " ").split())
  return normalized or "this is blank"


def _get_llm_mode() -> str:
  mode = (_LLM_MODE or "remote_only").strip().lower()
  if mode in {"remote", "remote_only"}:
    return "remote_only"
  if mode == "hybrid":
    return "hybrid"
  if mode == "local_only":
    return "local_only"
  return "remote_only"


def llm_local_only_mode() -> bool:
  return _get_llm_mode() == "local_only"


def llm_hybrid_mode() -> bool:
  return _get_llm_mode() == "hybrid"


def llm_allows_local_fallback() -> bool:
  return _get_llm_mode() in {"hybrid", "local_only"}


def _get_embedding_mode() -> str:
  mode = (_EMBEDDING_MODE or "hybrid").strip().lower()
  if mode not in {"hybrid", "remote_only", "local_only"}:
    return "hybrid"
  return mode


def _get_cached_embedding(text: str):
  if not _EMBEDDING_CACHE_ENABLED:
    return None
  if text not in _embedding_cache:
    return None
  value = _embedding_cache.pop(text)
  _embedding_cache[text] = value
  return value


def _set_cached_embedding(text: str, embedding):
  if not _EMBEDDING_CACHE_ENABLED:
    return embedding
  if text in _embedding_cache:
    _embedding_cache.pop(text)
  _embedding_cache[text] = embedding
  while len(_embedding_cache) > _EMBEDDING_CACHE_MAX_ENTRIES:
    _embedding_cache.popitem(last=False)
  return embedding


def _record_embedding_remote_success():
  _embedding_health["consecutive_failures"] = 0
  _embedding_health["last_failure_at"] = None
  _embedding_health["cooldown_until"] = 0.0


def _record_embedding_remote_failure(now_ts: Optional[float] = None):
  now_ts = time.time() if now_ts is None else now_ts
  _embedding_health["consecutive_failures"] += 1
  _embedding_health["last_failure_at"] = now_ts
  if _embedding_health["consecutive_failures"] >= _EMBEDDING_REMOTE_FAILURE_THRESHOLD:
    _embedding_health["cooldown_until"] = now_ts + _EMBEDDING_REMOTE_COOLDOWN_SECONDS


def _embedding_remote_allowed(now_ts: Optional[float] = None) -> bool:
  if _get_embedding_mode() != "hybrid":
    return _get_embedding_mode() == "remote_only"
  now_ts = time.time() if now_ts is None else now_ts
  return now_ts >= float(_embedding_health.get("cooldown_until", 0.0) or 0.0)


def _embedding_preflight_target():
  endpoint = openai_config.get("embeddings-endpoint") or "https://api.openai.com"
  endpoint = endpoint if "://" in endpoint else f"https://{endpoint}"
  parsed = urlparse(endpoint)
  host = parsed.hostname or "api.openai.com"
  port = parsed.port or (443 if parsed.scheme == "https" else 80)
  return host, port


def _embedding_network_preflight():
  if not _EMBEDDING_NETWORK_PREFLIGHT_ENABLED:
    return True, {"enabled": False}

  host, port = _embedding_preflight_target()
  wall_start = time.perf_counter()
  try:
    with socket.create_connection((host, port), timeout=_EMBEDDING_PREFLIGHT_TIMEOUT_SECONDS):
      return True, {
        "enabled": True,
        "host": host,
        "port": port,
        "timeout_seconds": _EMBEDDING_PREFLIGHT_TIMEOUT_SECONDS,
        "elapsed_seconds": time.perf_counter() - wall_start,
      }
  except OSError as exc:
    return False, {
      "enabled": True,
      "host": host,
      "port": port,
      "timeout_seconds": _EMBEDDING_PREFLIGHT_TIMEOUT_SECONDS,
      "elapsed_seconds": time.perf_counter() - wall_start,
      "error": str(exc),
    }


def _embedding_request_with_deadline(text: str, model: str):
  result_queue = queue.Queue(maxsize=1)

  def worker():
    try:
      response = embeddings_client.embeddings.create(
        input=[text],
        model=model,
        timeout=_EMBEDDING_TIMEOUT_SECONDS,
      )
      result_queue.put((True, response))
    except BaseException as exc:
      result_queue.put((False, exc))

  thread = threading.Thread(target=worker, daemon=True)
  thread.start()
  thread.join(_EMBEDDING_TIMEOUT_SECONDS)
  if thread.is_alive():
    raise TimeoutError(
      f"embedding request exceeded hard deadline {_EMBEDDING_TIMEOUT_SECONDS}s"
    )

  ok, payload = result_queue.get_nowait()
  if ok:
    return payload
  raise payload


def _local_embedding_with_cache(text: str):
  return _set_cached_embedding(text, _deterministic_local_embedding(text))


def reset_embedding_runtime_state():
  _embedding_cache.clear()
  _embedding_health["consecutive_failures"] = 0
  _embedding_health["last_failure_at"] = None
  _embedding_health["cooldown_until"] = 0.0


def _extract_response_text(payload):
  """Extract model text from different response schemas."""
  if isinstance(payload, dict):
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
      first = choices[0]
      if isinstance(first, dict):
        message = first.get("message")
        if isinstance(message, dict):
          content = message.get("content")
          if isinstance(content, str):
            return content
          if isinstance(content, list):
            txt = []
            for item in content:
              if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                  txt.append(item["text"])
                elif isinstance(item.get("content"), str):
                  txt.append(item["content"])
              elif isinstance(item, str):
                txt.append(item)
            if txt:
              return "\n".join(txt)
        if isinstance(first.get("text"), str):
          return first["text"]

    for key in ("output_text", "response", "output", "text", "content", "result"):
      if isinstance(payload.get(key), str):
        return payload[key]

    data = payload.get("data")
    if isinstance(data, dict):
      for key in ("text", "response", "output", "content"):
        if isinstance(data.get(key), str):
          return data[key]

  if isinstance(payload, str):
    return payload
  raise ValueError(f"Cannot parse text from response payload keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)}")


def _post_start_payload_via_curl(url: str, payload: dict) -> dict:
  wall_start = time.perf_counter()
  log_runtime_event(
    "llm start request begin",
    sim_code=static_sim_code,
    extra={"url": url, "model": payload.get("model"), "max_tokens": payload.get("max_tokens")},
  )
  command = [
    "curl.exe",
    "-sS",
    "--max-time",
    str(_START_TIMEOUT_SECONDS),
    "-X",
    "POST",
    url,
    "-H",
    "accept: application/json",
    "-H",
    f"Authorization: Bearer {openai_config['model-key']}",
    "-H",
    "Content-Type: application/json",
    "-d",
    json.dumps(payload, ensure_ascii=False),
  ]
  completed = subprocess.run(
    command,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=_START_TIMEOUT_SECONDS + 5,
    check=False,
  )
  if completed.returncode != 0:
    detail = completed.stderr.strip() or completed.stdout.strip()
    log_runtime_event(
      "llm start request failed",
      sim_code=static_sim_code,
      elapsed_seconds=time.perf_counter() - wall_start,
      extra={"detail": detail},
    )
    raise RuntimeError(f"curl.exe failed: {detail}")
  try:
    response_json = json.loads(completed.stdout)
  except json.JSONDecodeError as exc:
    raise RuntimeError(f"curl.exe returned non-JSON response: {completed.stdout[:500]}") from exc
  if response_json.get("success") is False:
    log_runtime_event(
      "llm start request failed",
      sim_code=static_sim_code,
      elapsed_seconds=time.perf_counter() - wall_start,
      extra={"detail": str(response_json.get("message") or response_json)},
    )
    raise RuntimeError(str(response_json.get("message") or response_json))
  log_runtime_event(
    "llm start request done",
    sim_code=static_sim_code,
    elapsed_seconds=time.perf_counter() - wall_start,
    extra={"url": url, "model": payload.get("model")},
  )
  return response_json


def _raw_start_chat_request(prompt: str, gpt_parameter: Optional[dict] = None) -> str:
  if not _MODEL_ENDPOINT:
    raise RuntimeError("OPENAI_ENDPOINT/model-endpoint is required for /api/v1/start mode.")

  payload = {
    "model": openai_config["model"],
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": prompt}
        ]
      }
    ],
    "temperature": 0,
    "n": 1,
    "stream": False,
  }
  if gpt_parameter:
    payload["model"] = gpt_parameter.get("engine", payload["model"])
    payload["temperature"] = gpt_parameter.get("temperature", payload["temperature"])
    if gpt_parameter.get("top_p") is not None:
      payload["top_p"] = gpt_parameter["top_p"]
    if gpt_parameter.get("frequency_penalty") is not None:
      payload["frequency_penalty"] = gpt_parameter["frequency_penalty"]
    if gpt_parameter.get("presence_penalty") is not None:
      payload["presence_penalty"] = gpt_parameter["presence_penalty"]
    if gpt_parameter.get("max_tokens") is not None:
      payload["max_tokens"] = gpt_parameter["max_tokens"]

  response_json = _post_start_payload_via_curl(_build_start_api_url(_MODEL_ENDPOINT), payload)
  return _extract_response_text(response_json)


def _deterministic_local_embedding(text: str, dim: int = _LOCAL_EMBED_DIM):
  # Hash-based deterministic pseudo-embedding used when no embedding API is available.
  raw = hashlib.sha256(text.encode("utf-8")).digest()
  vec = []
  i = 0
  while len(vec) < dim:
    block = hashlib.sha256(raw + str(i).encode("utf-8")).digest()
    for b in block:
      vec.append((b / 255.0) * 2 - 1)
      if len(vec) == dim:
        break
    i += 1
  return vec

if openai_config["client"] == "azure":
  client = setup_client("azure", {
      "endpoint": openai_config["model-endpoint"],
      "key": openai_config["model-key"],
      "api-version": openai_config["model-api-version"],
  })
elif openai_config["client"] == "openai":
  client = setup_client("openai", {
      "key": openai_config["model-key"],
      "endpoint": openai_config.get("model-endpoint", ""),
  })

if openai_config["embeddings-client"] == "azure":  
  embeddings_client = setup_client("azure", {
      "endpoint": openai_config["embeddings-endpoint"],
      "key": openai_config["embeddings-key"],
      "api-version": openai_config["embeddings-api-version"],
      "timeout": _EMBEDDING_TIMEOUT_SECONDS,
  })
elif openai_config["embeddings-client"] == "openai":
  embeddings_client = setup_client("openai", {
      "key": openai_config["embeddings-key"],
      "endpoint": openai_config.get("embeddings-endpoint", ""),
      "timeout": _EMBEDDING_TIMEOUT_SECONDS,
  })
else:
  raise ValueError("Invalid embeddings client")

cost_logger = OpenAICostLogger_Singleton(
  experiment_name = openai_config["experiment-name"],
  log_folder = DEFAULT_LOG_PATH,
  cost_upperbound = openai_config["cost-upperbound"]
)


def temp_sleep(seconds=0.1):
  time.sleep(seconds)


def ChatGPT_single_request(prompt):
  temp_sleep()
  total_wall_start = time.perf_counter()
  for attempt, delay in enumerate(_RETRY_DELAYS + [None]):
    try:
      log_runtime_event(
        "llm chat single begin",
        sim_code=static_sim_code,
        extra=_llm_extra(prompt, attempt=attempt + 1),
      )
      if _USE_START_ENDPOINT:
        response = _raw_start_chat_request(prompt)
      else:
        completion = client.chat.completions.create(
          model=openai_config["model"],
          messages=[{"role": "user", "content": prompt}]
        )
        cost_logger.update_cost(completion, input_cost=openai_config["model-costs"]["input"], output_cost=openai_config["model-costs"]["output"])
        response = completion.choices[0].message.content
      log_runtime_event(
        "llm chat single done",
        sim_code=static_sim_code,
        elapsed_seconds=time.perf_counter() - total_wall_start,
        extra=_llm_extra(prompt, attempt=attempt + 1),
      )
      return response
    except Exception as e:
      if delay is not None and _is_retryable(e):
        log_runtime_event(
          "llm chat single retry",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra=_llm_extra(prompt, attempt=attempt + 1, retry_delay_seconds=delay, error=str(e)),
        )
        print(f"ChatGPT_single_request retry {attempt+1}/{len(_RETRY_DELAYS)}, "
              f"waiting {delay}s: {e}")
        time.sleep(delay)
      else:
        log_runtime_event(
          "llm chat single failed",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra=_llm_extra(prompt, attempt=attempt + 1, error=str(e)),
        )
        raise


def ChatGPT_request(prompt):
  """
  Given a prompt and a dictionary of GPT parameters, make a request to OpenAI
  server and returns the response.
  ARGS:
    prompt: a str prompt
    gpt_parameter: a python dictionary with the keys indicating the names of
                   the parameter and the values indicating the parameter
                   values.
  RETURNS:
    a str of GPT-3's response.
  """
  # temp_sleep()
  total_wall_start = time.perf_counter()
  for attempt, delay in enumerate(_RETRY_DELAYS + [None]):
    try:
      log_runtime_event(
        "llm chat request begin",
        sim_code=static_sim_code,
        extra=_llm_extra(prompt, attempt=attempt + 1),
      )
      if _USE_START_ENDPOINT:
        response = _raw_start_chat_request(prompt)
      else:
        completion = client.chat.completions.create(
        model=openai_config["model"],
        messages=[{"role": "user", "content": prompt}]
        )
        cost_logger.update_cost(completion, input_cost=openai_config["model-costs"]["input"], output_cost=openai_config["model-costs"]["output"])
        response = completion.choices[0].message.content
      log_runtime_event(
        "llm chat request done",
        sim_code=static_sim_code,
        elapsed_seconds=time.perf_counter() - total_wall_start,
        extra=_llm_extra(prompt, attempt=attempt + 1),
      )
      return response
    except Exception as e:
      if delay is not None and _is_retryable(e):
        log_runtime_event(
          "llm chat request retry",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra=_llm_extra(prompt, attempt=attempt + 1, retry_delay_seconds=delay, error=str(e)),
        )
        print(f"ChatGPT_request retry {attempt+1}/{len(_RETRY_DELAYS)}, "
              f"waiting {delay}s: {e}")
        time.sleep(delay)
      else:
        log_runtime_event(
          "llm chat request failed",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra=_llm_extra(prompt, attempt=attempt + 1, error=str(e)),
        )
        print(f"Error: {e}")
        return "ChatGPT ERROR"


def ChatGPT_safe_generate_response(prompt, 
                                   example_output,
                                   special_instruction,
                                   repeat=3,
                                   fail_safe_response="error",
                                   func_validate=None,
                                   func_clean_up=None,
                                   verbose=False): 
  # prompt = 'GPT-3 Prompt:\n"""\n' + prompt + '\n"""\n'
  prompt = '"""\n' + prompt + '\n"""\n'
  prompt += f"Output the response to the prompt above in json. {special_instruction}\n"
  prompt += "Example output json:\n"
  prompt += '{"output": "' + str(example_output) + '"}'

  if verbose: 
    print ("CHAT GPT PROMPT")
    print (prompt)

  if llm_local_only_mode():
    log_runtime_event(
      "llm safe request local short-circuit",
      sim_code=static_sim_code,
      extra=_llm_extra(prompt, mode="local_only"),
    )
    return fail_safe_response

  for i in range(repeat): 

    try: 
      curr_gpt_response = ChatGPT_request(prompt).strip()
      end_index = curr_gpt_response.rfind('}') + 1
      curr_gpt_response = curr_gpt_response[:end_index]
      curr_gpt_response = json.loads(curr_gpt_response)["output"]
      
      if func_validate(curr_gpt_response, prompt=prompt): 
        return func_clean_up(curr_gpt_response, prompt=prompt)
      
      if verbose: 
        print ("---- repeat count: \n", i, curr_gpt_response)
        print (curr_gpt_response)
        print ("~~~~")

    except: 
      pass

  if llm_hybrid_mode():
    log_runtime_event(
      "llm safe request hybrid fallback",
      sim_code=static_sim_code,
      extra=_llm_extra(prompt, mode="hybrid"),
    )
    return fail_safe_response

  return False


def ChatGPT_safe_generate_response_OLD(prompt, 
                                   repeat=3,
                                   fail_safe_response="error",
                                   func_validate=None,
                                   func_clean_up=None,
                                   verbose=True): 
  if verbose: 
    print ("CHAT GPT PROMPT")
    print (prompt)

  if llm_local_only_mode():
    log_runtime_event(
      "llm safe legacy request local short-circuit",
      sim_code=static_sim_code,
      extra=_llm_extra(prompt, mode="local_only"),
    )
    return fail_safe_response

  for i in range(repeat): 
    try: 
      curr_gpt_response = ChatGPT_request(prompt).strip()
      print(curr_gpt_response)
      if func_validate(curr_gpt_response, prompt=prompt): 
        return func_clean_up(curr_gpt_response, prompt=prompt)
      if verbose: 
        print (f"---- repeat count: {i}")
        print (curr_gpt_response)
        print ("~~~~")

    except: 
      pass
  if llm_hybrid_mode():
    log_runtime_event(
      "llm safe legacy request hybrid fallback",
      sim_code=static_sim_code,
      extra=_llm_extra(prompt, mode="hybrid"),
    )
    return fail_safe_response
  print ("FAIL SAFE TRIGGERED") 
  return fail_safe_response


def GPT_request(prompt, gpt_parameter):
  """
  Given a prompt and a dictionary of GPT parameters, make a request to OpenAI
  server and returns the response.
  ARGS:
    prompt: a str prompt
    gpt_parameter: a python dictionary with the keys indicating the names of
                   the parameter and the values indicating the parameter
                   values.
  RETURNS:
    a str of GPT-3's response.
  """
  temp_sleep()
  total_wall_start = time.perf_counter()
  for attempt, delay in enumerate(_RETRY_DELAYS + [None]):
    try:
      log_runtime_event(
        "llm structured request begin",
        sim_code=static_sim_code,
        extra=_llm_extra(prompt, attempt=attempt + 1, engine=gpt_parameter.get("engine")),
      )
      if _USE_START_ENDPOINT:
        response_text = _raw_start_chat_request(prompt, gpt_parameter=gpt_parameter)
      else:
        messages = [{
          "role": "system", "content": prompt
        }]
        response = client.chat.completions.create(
                    model=gpt_parameter["engine"],
                    messages=messages,
                    temperature=gpt_parameter["temperature"],
                    max_tokens=gpt_parameter["max_tokens"],
                    top_p=gpt_parameter["top_p"],
                    frequency_penalty=gpt_parameter["frequency_penalty"],
                    presence_penalty=gpt_parameter["presence_penalty"],
                    stream=gpt_parameter["stream"],
                    stop=gpt_parameter["stop"],)
        cost_logger.update_cost(response=response, input_cost=openai_config["model-costs"]["input"], output_cost=openai_config["model-costs"]["output"])
        response_text = response.choices[0].message.content
      log_runtime_event(
        "llm structured request done",
        sim_code=static_sim_code,
        elapsed_seconds=time.perf_counter() - total_wall_start,
        extra=_llm_extra(prompt, attempt=attempt + 1, engine=gpt_parameter.get("engine")),
      )
      return response_text
    except Exception as e:
      if delay is not None and _is_retryable(e):
        log_runtime_event(
          "llm structured request retry",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra=_llm_extra(prompt, attempt=attempt + 1, engine=gpt_parameter.get("engine"), retry_delay_seconds=delay, error=str(e)),
        )
        print(f"GPT_request retry {attempt+1}/{len(_RETRY_DELAYS)}, "
              f"waiting {delay}s: {e}")
        time.sleep(delay)
      else:
        log_runtime_event(
          "llm structured request failed",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra=_llm_extra(prompt, attempt=attempt + 1, engine=gpt_parameter.get("engine"), error=str(e)),
        )
        print(f"Error: {e}")
        return "TOKEN LIMIT EXCEEDED"


def generate_prompt(curr_input, prompt_lib_file): 
  """
  Takes in the current input (e.g. comment that you want to classifiy) and 
  the path to a prompt file. The prompt file contains the raw str prompt that
  will be used, which contains the following substr: !<INPUT>! -- this 
  function replaces this substr with the actual curr_input to produce the 
  final promopt that will be sent to the GPT3 server. 
  ARGS:
    curr_input: the input we want to feed in (IF THERE ARE MORE THAN ONE
                INPUT, THIS CAN BE A LIST.)
    prompt_lib_file: the path to the promopt file. 
  RETURNS: 
    a str prompt that will be sent to OpenAI's GPT server.  
  """
  if type(curr_input) == type("string"): 
    curr_input = [curr_input]
  curr_input = [str(i) for i in curr_input]

  f = open(prompt_lib_file, "r", encoding="utf-8")
  prompt = f.read()
  f.close()
  for count, i in enumerate(curr_input):   
    prompt = prompt.replace(f"!<INPUT {count}>!", i)
  if "<commentblockmarker>###</commentblockmarker>" in prompt: 
    prompt = prompt.split("<commentblockmarker>###</commentblockmarker>")[1]
  return prompt.strip()


def safe_generate_response(prompt, 
                           gpt_parameter,
                           repeat=5,
                           fail_safe_response="error",
                           func_validate=None,
                           func_clean_up=None,
                           verbose=False): 
  if verbose: 
    print (prompt)

  for i in range(repeat): 
    curr_gpt_response = GPT_request(prompt, gpt_parameter)
    try:
      if func_validate(curr_gpt_response, prompt=prompt): 
        return func_clean_up(curr_gpt_response, prompt=prompt)
      if verbose: 
        print ("---- repeat count: ", i, curr_gpt_response)
        print (curr_gpt_response)
        print ("~~~~")
    except:
      pass
  return fail_safe_response


def get_embedding(text, model=openai_config["embeddings"]):
  text = _normalize_embedding_text(text)
  cached = _get_cached_embedding(text)
  if cached is not None:
    log_runtime_event(
      "embedding cache hit",
      sim_code=static_sim_code,
      extra={"text_chars": len(text)},
    )
    return cached

  mode = _get_embedding_mode()
  if mode == "local_only":
    log_runtime_event(
      "embedding local-only short-circuit",
      sim_code=static_sim_code,
      extra={"text_chars": len(text)},
    )
    return _local_embedding_with_cache(text)
  if mode == "hybrid" and not _embedding_remote_allowed():
    log_runtime_event(
      "embedding hybrid cooldown short-circuit",
      sim_code=static_sim_code,
      extra={"text_chars": len(text), "cooldown_until": _embedding_health.get("cooldown_until", 0.0)},
    )
    return _local_embedding_with_cache(text)

  total_wall_start = time.perf_counter()
  if mode == "hybrid":
    preflight_ok, preflight_detail = _embedding_network_preflight()
    if not preflight_ok:
      _record_embedding_remote_failure()
      log_runtime_event(
        "embedding preflight fallback-local",
        sim_code=static_sim_code,
        elapsed_seconds=time.perf_counter() - total_wall_start,
        extra={"mode": mode, "text_chars": len(text), **preflight_detail},
      )
      return _local_embedding_with_cache(text)

  for attempt, delay in enumerate(_EMBEDDING_RETRY_DELAYS + [None]):
    try:
      log_runtime_event(
        "embedding request begin",
        sim_code=static_sim_code,
        extra={"attempt": attempt + 1, "mode": mode, "text_chars": len(text), "timeout_seconds": _EMBEDDING_TIMEOUT_SECONDS},
      )
      response = _embedding_request_with_deadline(text, model)
      cost_logger.update_cost(response=response, input_cost=openai_config["embeddings-costs"]["input"], output_cost=openai_config["embeddings-costs"]["output"])
      _record_embedding_remote_success()
      log_runtime_event(
        "embedding request done",
        sim_code=static_sim_code,
        elapsed_seconds=time.perf_counter() - total_wall_start,
        extra={"attempt": attempt + 1, "mode": mode, "text_chars": len(text)},
      )
      return _set_cached_embedding(text, response.data[0].embedding)
    except Exception as e:
      if delay is not None and _is_retryable(e):
        log_runtime_event(
          "embedding request retry",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra={"attempt": attempt + 1, "retry_delay_seconds": delay, "mode": mode, "error": str(e)},
        )
        print(f"get_embedding retry {attempt+1}/{len(_EMBEDDING_RETRY_DELAYS)}, "
              f"waiting {delay}s: {e}")
        time.sleep(delay)
      else:
        if mode == "remote_only":
          log_runtime_event(
            "embedding request failed",
            sim_code=static_sim_code,
            elapsed_seconds=time.perf_counter() - total_wall_start,
            extra={"attempt": attempt + 1, "mode": mode, "error": str(e)},
          )
          raise
        _record_embedding_remote_failure()
        log_runtime_event(
          "embedding request fallback-local",
          sim_code=static_sim_code,
          elapsed_seconds=time.perf_counter() - total_wall_start,
          extra={"attempt": attempt + 1, "mode": mode, "error": str(e)},
        )
        print(f"get_embedding failed after retries, switching to local embeddings: {e}")
        return _local_embedding_with_cache(text)


if __name__ == '__main__':
  gpt_parameter = {"engine": openai_config["model"], "max_tokens": 50, 
                   "temperature": 0, "top_p": 1, "stream": False,
                   "frequency_penalty": 0, "presence_penalty": 0, 
                   "stop": ['"']}
  curr_input = ["driving to a friend's house"]
  prompt_lib_file = "prompt_template/test_prompt_July5.txt"
  prompt = generate_prompt(curr_input, prompt_lib_file)

  def __func_validate(gpt_response): 
    if len(gpt_response.strip()) <= 1:
      return False
    if len(gpt_response.strip().split(" ")) > 1: 
      return False
    return True
  def __func_clean_up(gpt_response):
    cleaned_response = gpt_response.strip()
    return cleaned_response

  output = safe_generate_response(prompt, 
                                 gpt_parameter,
                                 5,
                                 "rest",
                                 __func_validate,
                                 __func_clean_up,
                                 True)

  print (output)
