from types import SimpleNamespace

import pytest

from persona.prompt_template import gpt_structure


class DummyCostLogger:
    def update_cost(self, **kwargs):
        return None


class SuccessEmbeddingsClient:
    def __init__(self, embedding):
        self.embedding = embedding
        self.calls = 0
        self.timeouts = []
        self.embeddings = self

    def create(self, input, model, timeout=None):
        self.calls += 1
        self.timeouts.append(timeout)
        return SimpleNamespace(data=[SimpleNamespace(embedding=self.embedding)])


class FailingEmbeddingsClient:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0
        self.timeouts = []
        self.embeddings = self

    def create(self, input, model, timeout=None):
        self.calls += 1
        self.timeouts.append(timeout)
        raise self.exc


class SlowEmbeddingsClient:
    def __init__(self):
        self.calls = 0
        self.embeddings = self

    def create(self, input, model, timeout=None):
        self.calls += 1
        gpt_structure.time.sleep(timeout + 1)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


@pytest.fixture(autouse=True)
def reset_embedding_state(monkeypatch):
    monkeypatch.setattr(gpt_structure, "cost_logger", DummyCostLogger())
    monkeypatch.setattr(gpt_structure, "_RETRY_DELAYS", [])
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_CACHE_ENABLED", True)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_CACHE_MAX_ENTRIES", 16)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_REMOTE_FAILURE_THRESHOLD", 1)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_REMOTE_COOLDOWN_SECONDS", 300)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_TIMEOUT_SECONDS", 2.0)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_NETWORK_PREFLIGHT_ENABLED", False)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_MODE", "hybrid")
    gpt_structure.reset_embedding_runtime_state()


def test_embedding_cache_reuses_previous_result(monkeypatch):
    client = SuccessEmbeddingsClient([0.1, 0.2, 0.3])
    monkeypatch.setattr(gpt_structure, "embeddings_client", client)

    first = gpt_structure.get_embedding("same text")
    second = gpt_structure.get_embedding("same\ntext")

    assert first == [0.1, 0.2, 0.3]
    assert second == [0.1, 0.2, 0.3]
    assert client.calls == 1
    assert client.timeouts == [2.0]


def test_embedding_hybrid_short_circuits_to_local_during_cooldown(monkeypatch):
    client = FailingEmbeddingsClient(RuntimeError("Connection error"))
    monkeypatch.setattr(gpt_structure, "embeddings_client", client)
    monkeypatch.setattr(gpt_structure.time, "time", lambda: 1000.0)

    first = gpt_structure.get_embedding("first text")
    second = gpt_structure.get_embedding("second text")

    assert isinstance(first, list)
    assert isinstance(second, list)
    assert client.calls == 1
    assert gpt_structure._embedding_health["consecutive_failures"] == 1
    assert gpt_structure._embedding_health["cooldown_until"] == 1300.0


def test_embedding_remote_only_raises_after_failure(monkeypatch):
    client = FailingEmbeddingsClient(RuntimeError("Connection error"))
    monkeypatch.setattr(gpt_structure, "embeddings_client", client)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_MODE", "remote_only")

    with pytest.raises(RuntimeError, match="Connection error"):
        gpt_structure.get_embedding("remote only text")

    assert client.calls == 1


def test_embedding_uses_embedding_specific_retry_schedule(monkeypatch):
    client = FailingEmbeddingsClient(RuntimeError("rate limit"))
    sleep_calls = []

    monkeypatch.setattr(gpt_structure, "embeddings_client", client)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_RETRY_DELAYS", [0.5, 1.5])
    monkeypatch.setattr(gpt_structure.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = gpt_structure.get_embedding("retrying text")

    assert isinstance(result, list)
    assert client.calls == 3
    assert sleep_calls == [0.5, 1.5]


def test_embedding_hybrid_preflight_falls_back_before_remote_call(monkeypatch):
    client = SuccessEmbeddingsClient([0.1, 0.2, 0.3])
    monkeypatch.setattr(gpt_structure, "embeddings_client", client)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_NETWORK_PREFLIGHT_ENABLED", True)
    monkeypatch.setattr(
        gpt_structure,
        "_embedding_network_preflight",
        lambda: (False, {"enabled": True, "error": "network unreachable"}),
    )
    monkeypatch.setattr(gpt_structure.time, "time", lambda: 1000.0)

    result = gpt_structure.get_embedding("preflight fail")

    assert isinstance(result, list)
    assert client.calls == 0
    assert gpt_structure._embedding_health["consecutive_failures"] == 1
    assert gpt_structure._embedding_health["cooldown_until"] == 1300.0


def test_embedding_hard_deadline_falls_back_to_local(monkeypatch):
    client = SlowEmbeddingsClient()
    monkeypatch.setattr(gpt_structure, "embeddings_client", client)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(gpt_structure, "_EMBEDDING_RETRY_DELAYS", [])

    result = gpt_structure.get_embedding("slow remote")

    assert isinstance(result, list)
    assert client.calls == 1
    assert gpt_structure._embedding_health["consecutive_failures"] == 1


def test_safe_generate_old_short_circuits_in_local_only_mode(monkeypatch):
    monkeypatch.setattr(gpt_structure, "_LLM_MODE", "local_only")

    def should_not_run(*args, **kwargs):
        raise AssertionError("remote validator should not run in local_only mode")

    result = gpt_structure.ChatGPT_safe_generate_response_OLD(
        "prompt",
        fail_safe_response={"offline": True},
        func_validate=should_not_run,
        func_clean_up=should_not_run,
        verbose=False,
    )

    assert result == {"offline": True}


def test_safe_generate_old_hybrid_returns_fallback_without_fail_safe(monkeypatch, capsys):
    monkeypatch.setattr(gpt_structure, "_LLM_MODE", "hybrid")
    monkeypatch.setattr(gpt_structure, "ChatGPT_request", lambda prompt: "ChatGPT ERROR")

    result = gpt_structure.ChatGPT_safe_generate_response_OLD(
        "prompt",
        repeat=1,
        fail_safe_response={"offline": True},
        func_validate=lambda *_args, **_kwargs: False,
        func_clean_up=lambda value, **_kwargs: value,
        verbose=False,
    )

    captured = capsys.readouterr()
    assert result == {"offline": True}
    assert "FAIL SAFE TRIGGERED" not in captured.out


def test_safe_generate_hybrid_returns_fallback_response(monkeypatch):
    monkeypatch.setattr(gpt_structure, "_LLM_MODE", "hybrid")
    monkeypatch.setattr(gpt_structure, "ChatGPT_request", lambda prompt: "ChatGPT ERROR")

    result = gpt_structure.ChatGPT_safe_generate_response(
        "prompt",
        example_output="ok",
        special_instruction="Return json.",
        repeat=1,
        fail_safe_response={"offline": True},
        func_validate=lambda *_args, **_kwargs: False,
        func_clean_up=lambda value, **_kwargs: value,
        verbose=False,
    )

    assert result == {"offline": True}
