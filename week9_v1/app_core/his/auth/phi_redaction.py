from __future__ import annotations

from typing import Any


def redact_phi(payload: Any) -> Any:
    if isinstance(payload, str):
        return payload.replace("Patient ", "Patient#")
    if isinstance(payload, dict):
        cleaned = dict(payload)
        for key in ("full_name", "phone", "mrn"):
            if key in cleaned:
                cleaned[key] = "[REDACTED]"
        return cleaned
    return payload
