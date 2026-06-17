from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .correlation import correlate
from .models import ScenarioResult


def render_result_markdown(result: ScenarioResult, generated_at: datetime | None = None) -> str:
    stamp = generated_at if generated_at is not None else datetime.now(UTC)
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"# GreyNOC DMZ Scenario Report: {result.scenario_name}",
        "",
        f"Generated: {stamp.isoformat()}",
        f"Scenario ID: `{result.scenario_id}`",
        f"Status: `{status}`",
        "",
        "## Rule coverage",
        "",
        f"Expected: {', '.join(result.expected_rules) or 'none'}",
        f"Fired: {', '.join(result.fired_rules) or 'none'}",
        f"Missing: {', '.join(result.missing_rules) or 'none'}",
        f"Unexpected: {', '.join(result.unexpected_rules) or 'none'}",
        "",
        "## Incidents",
        "",
    ]

    incidents = correlate(result.alerts)
    if not incidents:
        lines.append("No incidents.")
    for incident in incidents:
        lines.extend(
            [
                f"### {incident.host} ({incident.severity.value})",
                "",
                f"Rules: {', '.join(incident.rule_ids)}",
                f"Tactics: {', '.join(incident.tactics) or 'none'}",
                f"Techniques: {', '.join(incident.techniques) or 'none'}",
                f"Alerts: `{incident.alert_count}` Events: `{incident.event_count}`",
                f"Window: `{incident.first_seen}` to `{incident.last_seen}` "
                f"(dwell `{incident.dwell_seconds:.0f}s`)",
                "",
            ]
        )

    lines.extend(["## Alerts", ""])
    if not result.alerts:
        lines.append("No alerts fired.")
    for alert in result.alerts:
        lines.extend(
            [
                f"### {alert.rule_id}: {alert.rule_name}",
                "",
                f"Severity: `{alert.severity.value}`",
                f"Host: `{alert.host}`",
                f"User: `{alert.user or 'n/a'}`",
                f"Events: `{alert.event_count}`",
                f"First seen: `{alert.first_seen}`",
                f"Last seen: `{alert.last_seen}`",
                f"Dwell: `{alert.dwell_seconds:.0f}s`",
                f"Runbook: `{alert.runbook or 'n/a'}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def write_report(
    result: ScenarioResult, output_dir: Path, generated_at: datetime | None = None
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{result.scenario_id}.md"
    path.write_text(render_result_markdown(result, generated_at), encoding="utf-8")
    return path
