from greynoc_dmz.access import Role, can
from greynoc_dmz.auth import (
    AuthConfig,
    SessionStore,
    build_clear_cookie,
    build_session_cookie,
    parse_cookie,
    verify_login,
)


def test_verify_login_when_auth_disabled() -> None:
    config = AuthConfig(enabled=False, username="admin", password=None, role=Role.admin)

    assert verify_login(config, "anyone", "anything") is True


def test_verify_login_when_auth_enabled() -> None:
    config = AuthConfig(enabled=True, username="admin", password="secret", role=Role.admin)

    assert verify_login(config, "admin", "secret") is True
    assert verify_login(config, "admin", "wrong") is False


def test_session_store_create_get_delete() -> None:
    store = SessionStore()
    session = store.create("admin", Role.admin)

    assert store.get(session.token) == session
    store.delete(session.token)
    assert store.get(session.token) is None


def test_session_cookie_helpers() -> None:
    store = SessionStore()
    session = store.create("admin", Role.admin)
    cookie = build_session_cookie(session, secure=False)

    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    assert parse_cookie(cookie) == session.token
    assert build_clear_cookie().endswith("Max-Age=0")


def test_role_permissions() -> None:
    assert can(Role.viewer, "dashboard:read") is True
    assert can(Role.viewer, "scenario:run") is False
    assert can(Role.engineer, "scenario:run") is True
    assert can(Role.admin, "system:admin") is True
