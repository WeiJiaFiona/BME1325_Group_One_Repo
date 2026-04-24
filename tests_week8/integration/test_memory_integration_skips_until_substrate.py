import importlib


def test_memory_service_import_smoke():
    assert importlib.import_module("app_core.memory.service") is not None
