from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from .config import load_lab_config
from .io import load_events, load_rules, load_scenario, write_json
from .models import Alert, DetectionRule, ScenarioResult, TelemetryEvent
from .store import append_history


def _value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    if isinstance(actual, str) and isinstance(expected, str):
        return expected.lower() in actual.lower()
    return bool(actual == expected)


def event_matches_rule(event: TelemetryEvent, rule: DetectionRule) -> bool:
    if rule.event_type and event.event_type != rule.event_type:
        return False

    for key, expected in rule.match.items():
        if key in {"message", "source", "host", "user", "ip", "event_type"}:
            actual = getattr(event, key)
        else:
            actual = event.fields.get(key)
        if not _value_matches(actual, expected):
            return False
    return True


def _threshold_window(events: list[TelemetryEvent], threshold: int, window_minutes: int) -> list[TelemetryEvent] | None:
    ordered = sorted(events, key=lambda item: item.timestamp)
    if len(ordered) < threshold:
        return None

    window = timedelta(minutes=window_minutes)
    for start in range(0, len(ordered) - threshold + 1):
        candidate = ordered[start : start + threshold]
        if candidate[-1].timestamp - candidate[0].timestamp <= window:
            return candidate
    return None


def run_rules(events: list[TelemetryEvent], rules: list[DetectionRule]) -> list[Alert]:
    alerts: list[Alert] = []
    for rule in rules:
        matches = [event for event in events if event_matches_rule(event, rule)]
        if len(matches) < rule.threshold:
            continue

        grouped: dict[tuple[str, str | None], list[TelemetryEvent]] = defaultdict(list)
        for event in matches:
            grouped[(event.host, event.user)].append(event)

        for (host, user), group in grouped.items():
            evidence = _threshold_window(group, rule.threshold, rule.window_minutes)
            if evidence is None:
                continue
            alerts.append(
                Alert(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    host=host,
                    user=user,
                    event_count=len(evidence),
                    first_seen=evidence[0].timestamp,
                    last_seen=evidence[-1].timestamp,
                    evidence=evidence,
                    runbook=rule.runbook,
                    mitre=rule.mitre,
                )
            )
    return sorted(alerts, key=lambda alert: (alert.severity.value, alert.rule_id))


def run_scenario(
    scenario_path: Path,
    rule_dir: Path,
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
    telemetry_root: Path | None = None,
) -> ScenarioResult:
    scenario = load_scenario(scenario_path)
    rules = load_rules(rule_dir)
    base = telemetry_root if telemetry_root is not None else scenario_path.parent.parent
    telemetry_path = base / scenario.telemetry_file
    events = load_events(telemetry_path)
    alerts = run_rules(events, rules)

    fired = sorted({alert.rule_id for alert in alerts})
    expected = sorted(scenario.expected_rules)
    missing = sorted(set(expected) - set(fired))
    unexpected = sorted(set(fired) - set(expected))

    result = ScenarioResult(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        passed=not missing and not unexpected,
        expected_rules=expected,
        fired_rules=fired,
        missing_rules=missing,
        unexpected_rules=unexpected,
        alerts=alerts,
    )

    if evidence_dir is not None:
        write_json(evidence_dir / f"{scenario.id}.json", result.model_dump(mode="json"))
    if history_dir is not None:
        append_history(history_dir, result)

    return result


def validate_all(root: Path, persist: bool = True) -> list[ScenarioResult]:
    config = load_lab_config(root)
    rule_dir = root / "detections" / "rules"
    evidence_dir = root / config.evidence_dir if persist else None
    history_dir = root / ".dmz" if persist else None
    scenario_paths = sorted((root / "scenarios").glob("*.json"))
    return [
        run_scenario(path, rule_dir, evidence_dir, history_dir, telemetry_root=root)
        for path in scenario_paths
    ]
