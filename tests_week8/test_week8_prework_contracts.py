import importlib
import os
import pytest


def test_memory_enabled_env_contract_defaults_on():
    # Default ON when unset.
    old = os.environ.pop("MEMORY_ENABLED", None)
    try:
        from tests_week8.support.fake_memory_service import env_flag

        assert env_flag("MEMORY_ENABLED", default="1") is True
    finally:
        if old is not None:
            os.environ["MEMORY_ENABLED"] = old


def test_memory_enabled_env_contract_explicit_off():
    old = os.environ.get("MEMORY_ENABLED")
    os.environ["MEMORY_ENABLED"] = "0"
    try:
        from tests_week8.support.fake_memory_service import env_flag

        assert env_flag("MEMORY_ENABLED", default="1") is False
    finally:
        if old is None:
            os.environ.pop("MEMORY_ENABLED", None)
        else:
            os.environ["MEMORY_ENABLED"] = old


def test_app_core_memory_not_present_yet_is_ok():
    # Prework stage: substrate may not exist yet.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app_core.memory")
