"""Auto-mode integration tests for Week8 memory.

This should later assert that week7 realism events (boarding timeout / resource bottleneck)
become replayable via the shared memory service.
"""

import importlib
import pytest


def _require_memory_service():
    try:
        return importlib.import_module("app_core.memory.service")
    except ModuleNotFoundError:
        pytest.skip("memory substrate not delivered yet")


def test_auto_boarding_timeout_is_captured():
    _require_memory_service()
    pytest.skip("auto hook integration not implemented in this prework step")
