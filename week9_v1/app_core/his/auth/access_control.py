from __future__ import annotations

from .permissions import ROLE_PERMISSIONS


def can_access(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    return "*" in perms or permission in perms
