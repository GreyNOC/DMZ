from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from ..models import ScenarioResult
from .models import Adapter, IntegrationResult, PublishContext, PublishOutcome
from .registry import register
from .transport import HttpResponse, TransportError, post_json


def _summary(result: ScenarioResult) -> dict[str, object]:
    return {
        "app": "greynoc-dmz",
        "kind": "scenario_result",
        "recorded_at": datetime.now(UTC).isoformat(),
        "scenario_id": result.scenario_id,
        "scenario_name": result.scenario_name,
        "passed": result.passed,
        "expected_rules": result.expected_rules,
        "fired_rules": result.fired_rules,
        "missing_rules": result.missing_rules,
        "unexpected_rules": result.unexpected_rules,
        "alert_count": len(result.alerts),
    }


def _outcome(
    ctx: PublishContext,
    scenario_id: str,
    outcome: PublishOutcome,
    target: str,
    detail: str,
) -> IntegrationResult:
    return IntegrationResult(
        integration=ctx.config.name,
        adapter=ctx.config.adapter,
        scenario_id=scenario_id,
        outcome=outcome,
        target=target,
        detail=detail,
    )


def _resolved_token(ctx: PublishContext) -> str | None:
    if ctx.token and ctx.token.strip():
        return ctx.token
    return None


def _interpret_http(
    ctx: PublishContext,
    scenario_id: str,
    target: str,
    response: HttpResponse,
    ok_detail: str,
) -> IntegrationResult:
    if response.ok:
        return _outcome(
            ctx, scenario_id, PublishOutcome.sent, target, f"{ok_detail} (HTTP {response.status})"
        )
    snippet = response.body.strip().replace("\n", " ")[:160]
    detail = f"HTTP {response.status}: {snippet}" if snippet else f"HTTP {response.status}"
    return _outcome(ctx, scenario_id, PublishOutcome.error, target, detail)


@register
class FileSink(Adapter):
    """Append scenario results to a local newline-delimited JSON file.

    Network-free. The safe default integration for an isolated lab and a simple
    feed for tools that tail a file.
    """

    name = "file"

    def publish_result(self, result: ScenarioResult, ctx: PublishContext) -> IntegrationResult:
        relative = ctx.config.options.get("path", "evidence/integration-outbox.ndjson")
        path = (ctx.root / relative).resolve()
        if ctx.dry_run:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.dry_run,
                str(path),
                f"dry-run: would append scenario {result.scenario_id} to {path}",
            )
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "integration": ctx.config.name,
            "result": result.model_dump(mode="json"),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
        return _outcome(
            ctx,
            result.scenario_id,
            PublishOutcome.sent,
            str(path),
            f"appended scenario {result.scenario_id}",
        )


@register
class WebhookAdapter(Adapter):
    """POST scenario results as JSON to any HTTP endpoint.

    Works with SOAR pipelines, MSP dashboards, chat webhooks, and EDR/XDR
    platforms that accept inbound JSON events. The credential is sent as a
    bearer token.
    """

    name = "webhook"
    requires = ("base_url", "token_env")

    def publish_result(self, result: ScenarioResult, ctx: PublishContext) -> IntegrationResult:
        url = ctx.config.base_url or ""
        token = _resolved_token(ctx)
        if token is None:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.error,
                url,
                f"credential env var '{ctx.config.token_env}' is not set",
            )
        if ctx.dry_run:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.dry_run,
                url,
                f"dry-run: would POST scenario {result.scenario_id} to {url}",
            )
        payload: dict[str, object] = {
            "app": "greynoc-dmz",
            "type": "scenario_result",
            "sent_at": datetime.now(UTC).isoformat(),
            "summary": _summary(result),
            "result": result.model_dump(mode="json"),
        }
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = post_json(
                url,
                payload,
                headers=headers,
                timeout=ctx.config.timeout_seconds,
                verify_tls=ctx.config.verify_tls,
            )
        except TransportError as error:
            return _outcome(ctx, result.scenario_id, PublishOutcome.error, url, str(error))
        return _interpret_http(ctx, result.scenario_id, url, response, "webhook accepted scenario")


@register
class SplunkHecAdapter(Adapter):
    """Send scenario results to a Splunk HTTP Event Collector endpoint."""

    name = "splunk_hec"
    requires = ("base_url", "token_env")

    def publish_result(self, result: ScenarioResult, ctx: PublishContext) -> IntegrationResult:
        base = (ctx.config.base_url or "").rstrip("/")
        url = f"{base}/services/collector/event"
        token = _resolved_token(ctx)
        if token is None:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.error,
                url,
                f"credential env var '{ctx.config.token_env}' is not set",
            )
        if ctx.dry_run:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.dry_run,
                url,
                f"dry-run: would send scenario {result.scenario_id} to Splunk HEC",
            )
        event: dict[str, object] = {
            "event": _summary(result),
            "sourcetype": ctx.config.options.get("sourcetype", "greynoc:dmz:validation"),
            "source": "greynoc-dmz",
        }
        index = ctx.config.options.get("index")
        if index:
            event["index"] = index
        headers = {"Authorization": f"Splunk {token}"}
        try:
            response = post_json(
                url,
                event,
                headers=headers,
                timeout=ctx.config.timeout_seconds,
                verify_tls=ctx.config.verify_tls,
            )
        except TransportError as error:
            return _outcome(ctx, result.scenario_id, PublishOutcome.error, url, str(error))
        return _interpret_http(ctx, result.scenario_id, url, response, "Splunk HEC accepted event")


@register
class JiraAdapter(Adapter):
    """Open a Jira issue when a scenario fails (a detection gap).

    Passing scenarios are skipped. Authentication uses Jira Basic auth: an
    account email plus an API token. Suited to MSP and SOC ticketing workflows.
    """

    name = "jira"
    requires = ("base_url", "token_env")
    required_options = ("email", "project")

    def publish_result(self, result: ScenarioResult, ctx: PublishContext) -> IntegrationResult:
        base = (ctx.config.base_url or "").rstrip("/")
        api_path = ctx.config.options.get("api_path", "/rest/api/2/issue")
        url = f"{base}{api_path}"
        if result.passed:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.skipped,
                url,
                f"scenario {result.scenario_id} passed; no ticket needed",
            )
        token = _resolved_token(ctx)
        if token is None:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.error,
                url,
                f"credential env var '{ctx.config.token_env}' is not set",
            )
        email = ctx.config.options.get("email", "")
        project = ctx.config.options.get("project", "")
        if not email or not project:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.error,
                url,
                "jira adapter needs options.email and options.project",
            )
        if ctx.dry_run:
            return _outcome(
                ctx,
                result.scenario_id,
                PublishOutcome.dry_run,
                url,
                f"dry-run: would open a {project} ticket for failed scenario {result.scenario_id}",
            )
        payload: dict[str, object] = {
            "fields": {
                "project": {"key": project},
                "summary": f"GreyNOC DMZ detection gap: {result.scenario_id}",
                "description": _jira_description(result),
                "issuetype": {"name": ctx.config.options.get("issue_type", "Task")},
            }
        }
        credentials = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
        headers = {"Authorization": f"Basic {credentials}"}
        try:
            response = post_json(
                url,
                payload,
                headers=headers,
                timeout=ctx.config.timeout_seconds,
                verify_tls=ctx.config.verify_tls,
            )
        except TransportError as error:
            return _outcome(ctx, result.scenario_id, PublishOutcome.error, url, str(error))
        if response.ok:
            key = _jira_issue_key(response.body)
            detail = f"opened ticket {key}" if key else f"opened ticket (HTTP {response.status})"
            return _outcome(ctx, result.scenario_id, PublishOutcome.sent, url, detail)
        return _interpret_http(ctx, result.scenario_id, url, response, "jira created issue")


def _jira_description(result: ScenarioResult) -> str:
    return "\n".join(
        [
            f"GreyNOC DMZ validation failed for scenario {result.scenario_id}.",
            "",
            f"Scenario: {result.scenario_name}",
            f"Expected rules: {', '.join(result.expected_rules) or 'none'}",
            f"Fired rules: {', '.join(result.fired_rules) or 'none'}",
            f"Missing rules: {', '.join(result.missing_rules) or 'none'}",
            f"Unexpected rules: {', '.join(result.unexpected_rules) or 'none'}",
            "",
            "Opened by greynoc-dmz integration-publish.",
        ]
    )


def _jira_issue_key(body: str) -> str | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        key = data.get("key")
        if isinstance(key, str):
            return key
    return None
