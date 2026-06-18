from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .engine import run_scenario
from .io import load_events, load_scenario
from .models import Scenario, ScenarioResult, TelemetryEvent

_CHAT_SYSTEM = (
    "You are a detection-engineering assistant. Given a window of synthetic "
    "security telemetry, identify which GreyNOC detection rules should fire."
)


class DatasetFormat(StrEnum):
    raw = "raw"
    chat = "chat"


@dataclass(frozen=True)
class ScenarioRun:
    """One scenario with its telemetry and validation result."""

    scenario: Scenario
    events: list[TelemetryEvent]
    result: ScenarioResult


def run_lab(root: Path) -> list[ScenarioRun]:
    """Run every scenario and return its scenario, telemetry, and result.

    No evidence or history files are written.
    """
    rule_dir = root / "detections" / "rules"
    runs: list[ScenarioRun] = []
    for path in sorted((root / "scenarios").glob("*.json")):
        scenario = load_scenario(path)
        events = load_events(root / scenario.telemetry_file)
        result = run_scenario(path, rule_dir)
        runs.append(ScenarioRun(scenario=scenario, events=events, result=result))
    return runs


def build_dataset(
    runs: list[ScenarioRun],
    fmt: DatasetFormat,
    ai_notes: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """Convert scenario runs into labeled training records.

    ``ai_notes`` maps a scenario id to an advisory AI analysis string.
    """
    notes = ai_notes or {}
    records: list[dict[str, object]] = []
    for run in runs:
        note = notes.get(run.scenario.id)
        if fmt is DatasetFormat.chat:
            records.append(_chat_record(run, note))
        else:
            records.append(_raw_record(run, note))
    return records


def write_dataset(records: list[dict[str, object]], path: Path) -> Path:
    """Write records as JSON Lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record))
            handle.write("\n")
    return path


def _raw_record(run: ScenarioRun, note: str | None) -> dict[str, object]:
    result = run.result
    return {
        "scenario_id": run.scenario.id,
        "scenario_name": run.scenario.name,
        "team": run.scenario.team,
        "telemetry": [event.model_dump(mode="json") for event in run.events],
        "expected_rules": result.expected_rules,
        "fired_rules": result.fired_rules,
        "missing_rules": result.missing_rules,
        "unexpected_rules": result.unexpected_rules,
        "passed": result.passed,
        "alerts": [alert.model_dump(mode="json") for alert in result.alerts],
        "ai_analysis": note,
    }


def _chat_record(run: ScenarioRun, note: str | None) -> dict[str, object]:
    return {
        "messages": [
            {"role": "system", "content": _CHAT_SYSTEM},
            {"role": "user", "content": _chat_user(run)},
            {"role": "assistant", "content": _chat_assistant(run, note)},
        ]
    }


def _chat_user(run: ScenarioRun) -> str:
    rendered = "\n".join(_render_event(event) for event in run.events)
    return (
        f"Scenario {run.scenario.id} telemetry window (synthetic lab data):\n\n"
        f"{rendered}\n\n"
        "Which GreyNOC detection rules should fire for this telemetry?"
    )


def _chat_assistant(run: ScenarioRun, note: str | None) -> str:
    result = run.result
    lines = [f"Expected detections: {', '.join(result.expected_rules) or 'none'}."]
    for alert in result.alerts:
        lines.append(
            f"- {alert.rule_id} ({alert.rule_name}): severity {alert.severity.value}, "
            f"host {alert.host}, {alert.event_count} events."
        )
    if note:
        lines.append("")
        lines.append(f"Analyst notes: {note}")
    return "\n".join(lines)


def _render_event(event: TelemetryEvent) -> str:
    parts = [event.timestamp.isoformat(), event.event_type, f"host={event.host}"]
    if event.user:
        parts.append(f"user={event.user}")
    if event.ip:
        parts.append(f"ip={event.ip}")
    parts.append(f"message={event.message!r}")
    return " ".join(parts)
