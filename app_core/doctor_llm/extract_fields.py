from __future__ import annotations

from typing import Any, Dict


def extract_fields_supplemental(
    *,
    patient_text: str,
    language: str,
    complaint_id: str,
    next_slot: str,
    filled_slots: Dict[str, Any],
) -> Dict[str, Any]:
    # Minimal safe implementation: do not override existing fields.
    # This hook is reserved for future model-assisted extraction.
    _ = (patient_text, language, complaint_id, next_slot)
    return {}

