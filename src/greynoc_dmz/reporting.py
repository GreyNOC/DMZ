from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

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
        "## Alerts",
        "",
    ]

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
