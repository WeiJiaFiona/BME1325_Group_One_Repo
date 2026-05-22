from __future__ import annotations

from typing import Any


def require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return require_str(value, field_name)


def require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    return dict(value)


def require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return list(value)


def ensure_list_of_dicts(value: Any, field_name: str) -> list[dict[str, Any]]:
    raw = require_list(value, field_name)
    cleaned: list[dict[str, Any]] = []
    for item in raw:
        cleaned.append(require_dict(item, field_name))
    return cleaned


def ensure_tags(value: Any, field_name: str) -> list[str]:
    raw = require_list(value, field_name)
    cleaned: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} items must be strings")
        cleaned.append(item)
    return cleaned
