"""Integration tests for Week8 memory hooks.

These tests are created early but are expected to SKIP until Developer A lands
`app_core/memory/*`.
"""

import importlib
import pytest


def _require_memory_service():
    try:
        mod = importlib.import_module("app_core.memory.service")
    except ModuleNotFoundError:
        pytest.skip("memory substrate not delivered yet")
    return mod


def test_user_mode_emits_minimum_events_in_order():
    _require_memory_service()
    # Placeholder: Once A delivers service and B integrates hooks, this test must:
    # 1) run a short user-mode interaction
    # 2) assert events include: encounter_started, vitals_measured, triage_completed, doctor_assessment_checkpoint, disposition_decided
    # 3) assert isolation keys run_id/mode/encounter_id/patient_id exist
    # 4) assert MemoryItem.step is strictly increasing
    pytest.skip("hook integration not implemented in this prework step")
