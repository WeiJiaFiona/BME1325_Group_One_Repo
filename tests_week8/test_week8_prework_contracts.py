import os
import importlib


def test_memory_enabled_env_contract_defaults_on():
    # Default ON when unset.
    old = os.environ.pop("MEMORY_V1_ENABLED", None)
    try:
        from app_core.memory.config import memory_v1_enabled

        assert memory_v1_enabled() is True
    finally:
        if old is not None:
            os.environ["MEMORY_V1_ENABLED"] = old


def test_memory_enabled_env_contract_explicit_off():
    old = os.environ.get("MEMORY_V1_ENABLED")
    os.environ["MEMORY_V1_ENABLED"] = "0"
    try:
        from app_core.memory.config import memory_v1_enabled

        assert memory_v1_enabled() is False
    finally:
        if old is None:
            os.environ.pop("MEMORY_V1_ENABLED", None)
        else:
            os.environ["MEMORY_V1_ENABLED"] = old


def test_app_core_memory_is_importable_now():
    assert importlib.import_module("app_core.memory.service") is not None
