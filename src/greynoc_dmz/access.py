from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    viewer = "viewer"
    analyst = "analyst"
    engineer = "engineer"
    admin = "admin"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.viewer: {"dashboard:read", "scenario:read", "report:read"},
    Role.analyst: {"dashboard:read", "scenario:read", "report:read", "evidence:read"},
    Role.engineer: {
        "dashboard:read",
        "scenario:read",
        "scenario:run",
        "report:read",
        "evidence:read",
        "rule:read",
        "rule:test",
    },
    Role.admin: {
        "dashboard:read",
        "scenario:read",
        "scenario:run",
        "report:read",
        "evidence:read",
        "rule:read",
        "rule:test",
        "system:admin",
    },
}


def can(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS[role]
