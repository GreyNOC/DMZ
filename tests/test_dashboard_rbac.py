import shutil
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from greynoc_dmz.access import Role, can
from greynoc_dmz.auth import AuthConfig, SessionStore, build_session_cookie
from greynoc_dmz.dashboard import ROUTE_PERMISSIONS, DashboardHandler

ROOT = Path(__file__).resolve().parents[1]


def test_route_policy_keeps_tooling_behind_engineer_role() -> None:
    # read-only roles see scenario status but not the detection tooling
    assert can(Role.viewer, ROUTE_PERMISSIONS["/"])
    assert can(Role.viewer, ROUTE_PERMISSIONS["/scenario"])
    assert not can(Role.viewer, ROUTE_PERMISSIONS["/coverage"])
    assert not can(Role.analyst, ROUTE_PERMISSIONS["/ai-battle"])
    # engineers and admins reach every dashboard route
    for permission in set(ROUTE_PERMISSIONS.values()):
        assert can(Role.engineer, permission)
        assert can(Role.admin, permission)


@pytest.fixture()
def viewer_server(tmp_path: Path) -> Iterator[tuple[str, str]]:
    for name in ("detections", "scenarios", "telemetry", "runbooks", "configs"):
        shutil.copytree(ROOT / name, tmp_path / name)

    sessions = SessionStore()
    session = sessions.create("viewer", Role.viewer)
    DashboardHandler.root = tmp_path
    DashboardHandler.auth_config = AuthConfig(
        enabled=True, username="viewer", password="secret", role=Role.viewer
    )
    DashboardHandler.sessions = sessions

    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    cookie = build_session_cookie(session, secure=False)
    try:
        yield f"http://{host}:{port}", cookie
    finally:
        server.shutdown()


def _status(url: str, cookie: str) -> int:
    request = urllib.request.Request(url, headers={"Cookie": cookie})
    try:
        with urllib.request.urlopen(request) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def test_viewer_is_forbidden_from_coverage(viewer_server: tuple[str, str]) -> None:
    base, cookie = viewer_server

    assert _status(f"{base}/", cookie) == 200
    assert _status(f"{base}/coverage", cookie) == 403
    assert _status(f"{base}/ai-battle", cookie) == 403
