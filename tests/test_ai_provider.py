import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from greynoc_dmz.ai import (
    AIConfig,
    AIProviderError,
    OpenAICompatibleProvider,
    run_live_check,
    run_scenario_review,
)
from greynoc_dmz.models import ScenarioResult


@dataclass
class CapturedRequest:
    path: str
    headers: dict[str, str]
    body: str


class RecordingServer(HTTPServer):
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


_COMPLETION = json.dumps(
    {
        "model": "test-model",
        "choices": [{"message": {"role": "assistant", "content": "Coverage looks solid."}}],
    }
)


@pytest.fixture
def server() -> Iterator[RecordingServer]:
    httpd = RecordingServer(("127.0.0.1", 0), _Handler)
    httpd.captured = []
    httpd.reply_status = 200
    httpd.reply_body = _COMPLETION
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def _config(server: RecordingServer, *, token_env: str | None = None) -> AIConfig:
    return AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url=f"http://127.0.0.1:{server.server_address[1]}/v1",
        model="test-model",
        token_env=token_env,
    )


def _result(*, passed: bool = True) -> ScenarioResult:
    return ScenarioResult(
        scenario_id="auth-bruteforce-sim",
        scenario_name="Test scenario",
        passed=passed,
        expected_rules=["GNOC-AUTH-001"],
        fired_rules=["GNOC-AUTH-001"] if passed else [],
        missing_rules=[] if passed else ["GNOC-AUTH-001"],
        unexpected_rules=[],
        alerts=[],
    )


def test_provider_completes_and_parses_content(server: RecordingServer) -> None:
    provider = OpenAICompatibleProvider(_config(server), token="sk-test")

    response = provider.complete("hello", system="be brief")

    assert response.text == "Coverage looks solid."
    assert response.model == "test-model"
    captured = server.captured[0]
    assert captured.path == "/v1/chat/completions"
    assert captured.headers["authorization"] == "Bearer sk-test"
    sent = json.loads(captured.body)
    assert sent["messages"][0]["role"] == "system"
    assert sent["messages"][1]["content"] == "hello"


def test_provider_without_token_sends_no_auth_header(server: RecordingServer) -> None:
    OpenAICompatibleProvider(_config(server), token=None).complete("hello")

    assert "authorization" not in server.captured[0].headers


def test_provider_http_error_does_not_leak_token(server: RecordingServer) -> None:
    server.reply_status = 500
    server.reply_body = "upstream error"
    provider = OpenAICompatibleProvider(_config(server), token="sk-supersecret")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "500" in str(excinfo.value)
    assert "sk-supersecret" not in str(excinfo.value)


def test_provider_non_json_response_raises(server: RecordingServer) -> None:
    server.reply_body = "not json at all"
    provider = OpenAICompatibleProvider(_config(server), token=None)

    with pytest.raises(AIProviderError):
        provider.complete("hello")


def test_provider_blocks_external_endpoint_without_allowance() -> None:
    config = AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
    )
    provider = OpenAICompatibleProvider(config, token="sk-test")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "blocked" in str(excinfo.value).lower()


def test_run_live_check_calls_provider(server: RecordingServer) -> None:
    server.reply_body = json.dumps({"choices": [{"message": {"content": "ready"}}]})

    response = run_live_check(_config(server))

    assert response.text == "ready"


def test_run_scenario_review_sends_synthetic_prompt(server: RecordingServer) -> None:
    response = run_scenario_review(_config(server), [_result(passed=False)])

    assert response.text == "Coverage looks solid."
    sent = json.loads(server.captured[0].body)
    assert "synthetic" in sent["messages"][1]["content"].lower()
