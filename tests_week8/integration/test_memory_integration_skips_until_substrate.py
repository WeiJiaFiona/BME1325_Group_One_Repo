import importlib
import pytest


def test_memory_service_import_skips_until_a_delivers_substrate():
    try:
        importlib.import_module("app_core.memory.service")
    except ModuleNotFoundError:
        pytest.skip("app_core/memory substrate not delivered by Developer A yet")
