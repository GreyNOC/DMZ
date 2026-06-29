import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from greynoc_dmz.integrations.transport import post_json

_target_auth_headers: list[str | None] = []


class _Target(BaseHTTPRequestHandler):
    def _record(self) -> None:
        _target_auth_headers.append(self.headers.get("Authorization"))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_POST(self) -> None:  # noqa: N802
        self._record()

    def do_GET(self) -> None:  # noqa: N802
        self._record()

    def log_message(self, *args: object) -> None:
        return


class _Redirector(BaseHTTPRequestHandler):
    target_url = ""

    def do_POST(self) -> None:  # noqa: N802
        self.send_response(302)
        self.send_header("Location", self.target_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def servers() -> Iterator[str]:
    _target_auth_headers.clear()
    target = HTTPServer(("127.0.0.1", 0), _Target)
    threading.Thread(target=target.serve_forever, daemon=True).start()
    _Redirector.target_url = f"http://127.0.0.1:{target.server_address[1]}/"
    redirector = HTTPServer(("127.0.0.1", 0), _Redirector)
    threading.Thread(target=redirector.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{redirector.server_address[1]}/"
    finally:
        redirector.shutdown()
        redirector.server_close()
        target.shutdown()
        target.server_close()


def test_post_json_does_not_follow_redirect(servers: str) -> None:
    response = post_json(
        servers, {"x": 1}, headers={"Authorization": "Bearer SECRET-KEY"}, timeout=5
    )

    # The 3xx is returned as-is (not followed), so adapters reject it via .ok.
    assert response.status == 302
    assert response.ok is False
    # The credential never reached the redirect target.
    assert _target_auth_headers == []
