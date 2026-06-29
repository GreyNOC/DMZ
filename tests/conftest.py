from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


@dataclass
class CapturedRequest:
    path: str
    headers: dict[str, str]
    body: str


class RecordingServer(HTTPServer):
    """A loopback HTTP server that records POSTs and replays a canned reply.

    Loopback endpoints are 'local' under the safety policy, so providers reach it
    without ``allow_external`` — letting provider adapters be exercised end to end
    with no real keys and no outbound traffic.
    """

    captured: list[CapturedRequest]
    reply_status: int
    reply_body: str


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        server = self.server
        assert isinstance(server, RecordingServer)
        server.captured.append(
            CapturedRequest(
                path=self.path,
                headers={key.lower(): value for key, value in self.headers.items()},
                body=body,
            )
        )
        payload = server.reply_body.encode("utf-8")
        self.send_response(server.reply_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def recording_server() -> Iterator[RecordingServer]:
    httpd = RecordingServer(("127.0.0.1", 0), _Handler)
    httpd.captured = []
    httpd.reply_status = 200
    httpd.reply_body = "{}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
