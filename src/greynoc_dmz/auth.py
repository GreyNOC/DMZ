from __future__ import annotations

import hmac
import os
import secrets
import time
from dataclasses import dataclass
from http import cookies

from .access import Role

SESSION_COOKIE = "greynoc_dmz_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    username: str
    password: str | None
    role: Role


@dataclass(frozen=True)
class Session:
    token: str
    username: str
    role: Role
    expires_at: float


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, username: str, role: Role) -> Session:
        token = secrets.token_urlsafe(32)
        session = Session(
            token=token,
            username=username,
            role=role,
            expires_at=time.time() + SESSION_TTL_SECONDS,
        )
        self._sessions[token] = session
        return session

    def get(self, token: str | None) -> Session | None:
        if not token:
            return None
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.expires_at < time.time():
            self._sessions.pop(token, None)
            return None
        return session

    def delete(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)


def load_auth_config() -> AuthConfig:
    password = os.environ.get("GREYNOC_DMZ_PASSWORD")
    username = os.environ.get("GREYNOC_DMZ_USERNAME", "admin")
    role_value = os.environ.get("GREYNOC_DMZ_ROLE", Role.admin.value)
    try:
        role = Role(role_value)
    except ValueError:
        role = Role.admin
    return AuthConfig(enabled=bool(password), username=username, password=password, role=role)


def verify_login(config: AuthConfig, username: str, password: str) -> bool:
    if not config.enabled or config.password is None:
        return True
    return hmac.compare_digest(username, config.username) and hmac.compare_digest(password, config.password)


def parse_cookie(header: str | None) -> str | None:
    if not header:
        return None
    jar = cookies.SimpleCookie()
    jar.load(header)
    morsel = jar.get(SESSION_COOKIE)
    if morsel is None:
        return None
    return morsel.value


def build_session_cookie(session: Session, secure: bool) -> str:
    parts = [
        f"{SESSION_COOKIE}={session.token}",
        "HttpOnly",
        "SameSite=Strict",
        "Path=/",
        f"Max-Age={SESSION_TTL_SECONDS}",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def build_clear_cookie() -> str:
    return f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
