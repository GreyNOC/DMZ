import json
import shutil
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from greynoc_dmz.access import Role
from greynoc_dmz.auth import AuthConfig, SessionStore, build_session_cookie
from greynoc_dmz.dashboard import ROUTE_PERMISSIONS, DashboardHandler

ROOT = Path(__file__).resolve().parents[1]


def _serve(tmp_path: Path) -> ThreadingHTTPServer:
    for name in ("detections", "scenarios", "telemetry", "runbooks", "configs"):
        shutil.copytree(ROOT / name, tmp_path / name)
    DashboardHandler.root = tmp_path
    DashboardHandler.sessions = SessionStore()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@pytest.fixture()
def admin_server(tmp_path: Path) -> Iterator[str]:
    DashboardHandler.auth_config = AuthConfig(
        enabled=False, username="admin", password=None, role=Role.admin
    )
    server = _serve(tmp_path)
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()


@pytest.fixture()
def viewer_server(tmp_path: Path) -> Iterator[tuple[str, str]]:
    sessions = SessionStore()
    session = sessions.create("viewer", Role.viewer)
    DashboardHandler.auth_config = AuthConfig(
        enabled=True, username="viewer", password="secret", role=Role.viewer
    )
    server = _serve(tmp_path)
    DashboardHandler.sessions = sessions
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", build_session_cookie(session, secure=False)
    finally:
        server.shutdown()


def test_roster_route_requires_engineer_role() -> None:
    assert ROUTE_PERMISSIONS["/roster"] == "rule:test"
    assert ROUTE_PERMISSIONS["/api/roster"] == "rule:test"


def test_admin_sees_roster_page(admin_server: str) -> None:
    with urllib.request.urlopen(f"{admin_server}/roster") as response:
        body = response.read().decode("utf-8")

    assert "AI battle roster" in body
    assert "Claude" in body


def test_admin_roster_api_returns_fighters(admin_server: str) -> None:
    with urllib.request.urlopen(f"{admin_server}/api/roster") as response:
        payload = json.loads(response.read().decode("utf-8"))

    names = {fighter["name"] for fighter in payload["fighters"]}
    assert {"Claude", "GPT", "Gemini"} <= names
    for fighter in payload["fighters"]:
        assert "status" in fighter


def test_viewer_is_forbidden_from_roster(viewer_server: tuple[str, str]) -> None:
    base, cookie = viewer_server
    request = urllib.request.Request(f"{base}/roster", headers={"Cookie": cookie})

    try:
        status = urllib.request.urlopen(request).status
    except urllib.error.HTTPError as exc:
        status = exc.code

    assert status == 403
