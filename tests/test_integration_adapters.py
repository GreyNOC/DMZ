import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from greynoc_dmz.integrations import (
    IntegrationConfig,
    IntegrationKind,
    PublishContext,
    PublishOutcome,
    SafetyPolicy,
    publish_all,
)
from greynoc_dmz.integrations.adapters import (
    FileSink,
    JiraAdapter,
    SplunkHecAdapter,
    WebhookAdapter,
)
from greynoc_dmz.models import ScenarioResult

_NO_EXTERNAL = SafetyPolicy(allow_external=False, allowlist=frozenset())


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


@pytest.fixture
def server() -> Iterator[RecordingServer]:
    httpd = RecordingServer(("127.0.0.1", 0), _Handler)
    httpd.captured = []
    httpd.reply_status = 200
    httpd.reply_body = '{"ok": true}'
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def _url(server: RecordingServer, path: str = "/") -> str:
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


def _scenario_result(*, passed: bool = True) -> ScenarioResult:
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


def _context(
    config: IntegrationConfig,
    root: Path,
    *,
    token: str | None = "secret",
    dry_run: bool = False,
) -> PublishContext:
    return PublishContext(config=config, token=token, dry_run=dry_run, root=root)


def test_file_sink_writes_ndjson(tmp_path: Path) -> None:
    config = IntegrationConfig(name="f", kind=IntegrationKind.file, adapter="file", enabled=True)

    outcome = FileSink().publish_result(_scenario_result(), _context(config, tmp_path, token=None))

    assert outcome.outcome == PublishOutcome.sent
    feed = tmp_path / "evidence" / "integration-outbox.ndjson"
    record = json.loads(feed.read_text(encoding="utf-8").splitlines()[0])
    assert record["result"]["scenario_id"] == "auth-bruteforce-sim"


def test_file_sink_dry_run_writes_nothing(tmp_path: Path) -> None:
    config = IntegrationConfig(name="f", kind=IntegrationKind.file, adapter="file", enabled=True)

    outcome = FileSink().publish_result(
        _scenario_result(), _context(config, tmp_path, token=None, dry_run=True)
    )

    assert outcome.outcome == PublishOutcome.dry_run
    assert not (tmp_path / "evidence" / "integration-outbox.ndjson").exists()


def test_webhook_posts_authenticated_json(server: RecordingServer, tmp_path: Path) -> None:
    config = IntegrationConfig(
        name="hook",
        kind=IntegrationKind.edr,
        adapter="webhook",
        enabled=True,
        base_url=_url(server, "/dmz"),
        token_env="DMZ_WEBHOOK_TOKEN",
    )

    outcome = WebhookAdapter().publish_result(
        _scenario_result(), _context(config, tmp_path, token="bearer-xyz")
    )

    assert outcome.outcome == PublishOutcome.sent
    captured = server.captured[0]
    assert captured.path == "/dmz"
    assert captured.headers["authorization"] == "Bearer bearer-xyz"
    assert json.loads(captured.body)["summary"]["scenario_id"] == "auth-bruteforce-sim"


def test_webhook_missing_token_is_error(server: RecordingServer, tmp_path: Path) -> None:
    config = IntegrationConfig(
        name="hook",
        kind=IntegrationKind.edr,
        adapter="webhook",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_WEBHOOK_TOKEN",
    )

    outcome = WebhookAdapter().publish_result(
        _scenario_result(), _context(config, tmp_path, token=None)
    )

    assert outcome.outcome == PublishOutcome.error
    assert "DMZ_WEBHOOK_TOKEN" in outcome.detail
    assert not server.captured


def test_webhook_dry_run_does_not_call_server(server: RecordingServer, tmp_path: Path) -> None:
    config = IntegrationConfig(
        name="hook",
        kind=IntegrationKind.edr,
        adapter="webhook",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_WEBHOOK_TOKEN",
    )

    outcome = WebhookAdapter().publish_result(
        _scenario_result(), _context(config, tmp_path, dry_run=True)
    )

    assert outcome.outcome == PublishOutcome.dry_run
    assert not server.captured


def test_webhook_error_response_hides_token(server: RecordingServer, tmp_path: Path) -> None:
    server.reply_status = 500
    server.reply_body = "internal error"
    config = IntegrationConfig(
        name="hook",
        kind=IntegrationKind.edr,
        adapter="webhook",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_WEBHOOK_TOKEN",
    )

    outcome = WebhookAdapter().publish_result(
        _scenario_result(), _context(config, tmp_path, token="topsecret")
    )

    assert outcome.outcome == PublishOutcome.error
    assert "500" in outcome.detail
    assert "topsecret" not in outcome.detail


def test_splunk_hec_sends_event(server: RecordingServer, tmp_path: Path) -> None:
    config = IntegrationConfig(
        name="splunk",
        kind=IntegrationKind.siem,
        adapter="splunk_hec",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_SPLUNK_HEC_TOKEN",
        options={"index": "greynoc_dmz"},
    )

    outcome = SplunkHecAdapter().publish_result(
        _scenario_result(), _context(config, tmp_path, token="hec-token")
    )

    assert outcome.outcome == PublishOutcome.sent
    captured = server.captured[0]
    assert captured.path == "/services/collector/event"
    assert captured.headers["authorization"] == "Splunk hec-token"
    body = json.loads(captured.body)
    assert body["event"]["scenario_id"] == "auth-bruteforce-sim"
    assert body["index"] == "greynoc_dmz"


def test_jira_opens_ticket_for_failed_scenario(server: RecordingServer, tmp_path: Path) -> None:
    server.reply_status = 201
    server.reply_body = '{"key": "SOC-42"}'
    config = IntegrationConfig(
        name="jira",
        kind=IntegrationKind.ticketing,
        adapter="jira",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_JIRA_API_TOKEN",
        options={"email": "bot@example.invalid", "project": "SOC"},
    )

    outcome = JiraAdapter().publish_result(
        _scenario_result(passed=False), _context(config, tmp_path, token="jira-token")
    )

    assert outcome.outcome == PublishOutcome.sent
    assert "SOC-42" in outcome.detail
    captured = server.captured[0]
    assert captured.path == "/rest/api/2/issue"
    assert captured.headers["authorization"].startswith("Basic ")
    assert json.loads(captured.body)["fields"]["project"]["key"] == "SOC"


def test_jira_skips_passing_scenario(server: RecordingServer, tmp_path: Path) -> None:
    config = IntegrationConfig(
        name="jira",
        kind=IntegrationKind.ticketing,
        adapter="jira",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_JIRA_API_TOKEN",
        options={"email": "bot@example.invalid", "project": "SOC"},
    )

    outcome = JiraAdapter().publish_result(
        _scenario_result(passed=True), _context(config, tmp_path, token="jira-token")
    )

    assert outcome.outcome == PublishOutcome.skipped
    assert not server.captured


def test_publish_all_blocks_external_endpoint(tmp_path: Path) -> None:
    config = IntegrationConfig(
        name="ext-siem",
        kind=IntegrationKind.siem,
        adapter="webhook",
        enabled=True,
        base_url="https://splunk.example.invalid:8088",
        token_env="DMZ_WEBHOOK_TOKEN",
    )

    outcomes = publish_all(
        [_scenario_result()], [config], dry_run=False, root=tmp_path, policy=_NO_EXTERNAL
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == PublishOutcome.blocked


def test_publish_all_sends_through_dispatch(
    server: RecordingServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DMZ_DISPATCH_TOKEN", "dispatch-token")
    config = IntegrationConfig(
        name="hook",
        kind=IntegrationKind.edr,
        adapter="webhook",
        enabled=True,
        base_url=_url(server),
        token_env="DMZ_DISPATCH_TOKEN",
    )

    outcomes = publish_all(
        [_scenario_result()], [config], dry_run=False, root=tmp_path, policy=_NO_EXTERNAL
    )

    assert outcomes[0].outcome == PublishOutcome.sent
    assert server.captured[0].headers["authorization"] == "Bearer dispatch-token"


def test_publish_all_dry_run_skips_file_write(tmp_path: Path) -> None:
    config = IntegrationConfig(name="f", kind=IntegrationKind.file, adapter="file", enabled=True)

    outcomes = publish_all(
        [_scenario_result()], [config], dry_run=True, root=tmp_path, policy=_NO_EXTERNAL
    )

    assert outcomes[0].outcome == PublishOutcome.dry_run
    assert not (tmp_path / "evidence" / "integration-outbox.ndjson").exists()
