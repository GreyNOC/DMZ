import json
import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from conftest import RecordingServer

from greynoc_dmz.access import Role
from greynoc_dmz.auth import AuthConfig, SessionStore, build_session_cookie
from greynoc_dmz.dashboard import DashboardHandler

ROOT = Path(__file__).resolve().parents[1]


def _openai_reply(content: str) -> str:
    return json.dumps({"model": "m", "choices": [{"message": {"content": content}}]})


def _lab_with_local_roster(
    tmp_path: Path, port: int, extra: list[dict[str, object]] | None = None
) -> None:
    for name in ("detections", "scenarios", "telemetry", "runbooks", "configs"):
        shutil.copytree(ROOT / name, tmp_path / name)
    fighters: list[dict[str, object]] = [
        {
            "name": name,
            "provider": "openai_compatible",
            "model": "m",
            "base_url": f"http://127.0.0.1:{port}/v1",
        }
        for name in ("Alpha", "Beta", "Judge")
    ]
    if extra:
        fighters.extend(extra)
    (tmp_path / "configs" / "ai-roster.json").write_text(
        json.dumps({"fighters": fighters}), encoding="utf-8"
    )


def _post(url: str, fields: list[tuple[str, str]], cookie: str | None = None) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    headers = {"Cookie": cookie} if cookie else {}
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8")


@pytest.fixture
def admin_arena(tmp_path: Path, recording_server: RecordingServer) -> Iterator[str]:
    recording_server.reply_body = _openai_reply(
        json.dumps(
            {
                "scores": {"Alpha": 8, "Beta": 5, "Red": 9, "Blue": 4},
                "winner": "Alpha",
                "rationale": "decisive",
            }
        )
    )
    _lab_with_local_roster(tmp_path, recording_server.server_address[1])
    DashboardHandler.root = tmp_path
    DashboardHandler.auth_config = AuthConfig(
        enabled=False, username="admin", password=None, role=Role.admin
    )
    DashboardHandler.sessions = SessionStore()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()


@pytest.fixture
def viewer_arena(tmp_path: Path, recording_server: RecordingServer) -> Iterator[tuple[str, str]]:
    _lab_with_local_roster(tmp_path, recording_server.server_address[1])
    sessions = SessionStore()
    session = sessions.create("viewer", Role.viewer)
    DashboardHandler.root = tmp_path
    DashboardHandler.auth_config = AuthConfig(
        enabled=True, username="viewer", password="secret", role=Role.viewer
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    DashboardHandler.sessions = sessions
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", build_session_cookie(session, secure=False)
    finally:
        server.shutdown()


def test_get_live_battle_shows_forms(admin_arena: str) -> None:
    with urllib.request.urlopen(f"{admin_arena}/live-battle") as response:
        body = response.read().decode("utf-8")

    assert "Live AI battle arena" in body
    assert 'action="/run-battle"' in body
    assert 'action="/run-collab"' in body
    assert "name='fighter'" in body or 'name="fighter"' in body


def test_post_run_battle_renders_result(admin_arena: str) -> None:
    status, body = _post(
        f"{admin_arena}/run-battle",
        [("fighter", "Alpha"), ("fighter", "Beta"), ("judge", "Judge"), ("rounds", "1")],
    )

    assert status == 200
    assert "Battle result" in body
    assert "Not ready" not in body
    assert "Alpha" in body


def test_post_run_battle_requires_two_fighters(admin_arena: str) -> None:
    status, body = _post(
        f"{admin_arena}/run-battle", [("fighter", "Alpha"), ("judge", "Judge"), ("rounds", "1")]
    )

    assert status == 200
    assert "at least two" in body


def test_post_run_collab_renders_result(admin_arena: str) -> None:
    status, body = _post(
        f"{admin_arena}/run-collab",
        [("teams", "Red=Alpha;Blue=Beta"), ("judge", "Judge"), ("rounds", "1")],
    )

    assert status == 200
    assert "Collaborative battle result" in body
    assert "Red" in body


def test_viewer_is_forbidden_from_live_battle(viewer_arena: tuple[str, str]) -> None:
    base, cookie = viewer_arena
    request = urllib.request.Request(f"{base}/live-battle", headers={"Cookie": cookie})

    try:
        status = urllib.request.urlopen(request).status
    except urllib.error.HTTPError as exc:
        status = exc.code

    assert status == 403


def test_viewer_is_forbidden_from_run_battle(viewer_arena: tuple[str, str]) -> None:
    base, cookie = viewer_arena

    status, _body = _post(
        f"{base}/run-battle", [("fighter", "Alpha"), ("fighter", "Beta")], cookie=cookie
    )

    assert status == 403


@pytest.fixture
def admin_arena_hosted(
    tmp_path: Path, recording_server: RecordingServer, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    # The key IS present, so the hosted fighter's only blocker is the external
    # endpoint — which makes the allow_external gate the single deciding factor.
    monkeypatch.setenv("DASH_TEST_KEY", "x")
    recording_server.reply_body = _openai_reply(
        json.dumps({"scores": {"Alpha": 8, "Beta": 5}, "winner": "Alpha"})
    )
    _lab_with_local_roster(
        tmp_path,
        recording_server.server_address[1],
        extra=[
            {
                "name": "Claude",
                "provider": "anthropic",
                "model": "claude-opus-4-8",
                "token_env": "DASH_TEST_KEY",
            }
        ],
    )
    DashboardHandler.root = tmp_path
    DashboardHandler.auth_config = AuthConfig(
        enabled=False, username="admin", password=None, role=Role.admin
    )
    DashboardHandler.sessions = SessionStore()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()


def test_run_battle_refuses_hosted_fighter_without_allow_external(admin_arena_hosted: str) -> None:
    # No allow_external checkbox: the hosted (external) fighter must be refused,
    # never silently run. A dropped gate or hardcoded allow_external=True would
    # instead attempt a real outbound call and fail this assertion.
    status, body = _post(
        f"{admin_arena_hosted}/run-battle",
        [("fighter", "Alpha"), ("fighter", "Claude"), ("judge", "Judge"), ("rounds", "1")],
    )

    assert status == 200
    assert "Not ready" in body
    assert "Allow external endpoints" in body
    assert "Battle result" not in body


def test_run_battle_refuses_hosted_judge_without_allow_external(admin_arena_hosted: str) -> None:
    status, body = _post(
        f"{admin_arena_hosted}/run-battle",
        [("fighter", "Alpha"), ("fighter", "Beta"), ("judge", "Claude"), ("rounds", "1")],
    )

    assert status == 200
    assert "Not ready" in body
    assert "Battle result" not in body


def test_run_collab_refuses_hosted_fighter_without_allow_external(admin_arena_hosted: str) -> None:
    status, body = _post(
        f"{admin_arena_hosted}/run-collab",
        [("teams", "Red=Alpha;Blue=Claude"), ("judge", "Judge"), ("rounds", "1")],
    )

    assert status == 200
    assert "Not ready" in body
    assert "Collaborative battle result" not in body
