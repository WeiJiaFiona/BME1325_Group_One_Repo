from __future__ import annotations

import pytest


def test_user_flow_integration_waits_for_storage_gate() -> None:
    pytest.importorskip(
        "app_core.his.storage.base",
        reason="Developer A storage/base gate is not present in the fetched upload yet.",
    )
    pytest.skip("TODO: wire user-mode ED checkpoints through HIS services once the storage gate is available.")
