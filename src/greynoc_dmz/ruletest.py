from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from .engine import run_rules
from .io import load_rules, read_json
from .models import TelemetryEvent

_EVENTS = TypeAdapter(list[TelemetryEvent])


@dataclass(frozen=True)
class RuleTestResult:
    rule_id: str
    passed: bool
    detail: str


def _events(raw: Any) -> list[TelemetryEvent]:
    return _EVENTS.validate_python(raw or [])


def run_rule_tests(root: Path) -> list[RuleTestResult]:
    """Run true-positive / true-negative cases under ``detections/tests``.

    Each test file is ``{"rule_id": ..., "true_positive": [...], "true_negative": [...]}``.
    A rule passes when its true-positive events make it fire and its
    true-negative events do not.
    """
    rules = {rule.id: rule for rule in load_rules(root / "detections" / "rules")}
    results: list[RuleTestResult] = []

    for path in sorted((root / "detections" / "tests").glob("*.json")):
        raw = read_json(path)
        if not isinstance(raw, dict):
            results.append(RuleTestResult(path.stem, False, "test file is not an object"))
            continue

        rule_id = str(raw.get("rule_id") or path.stem)
        rule = rules.get(rule_id)
        if rule is None:
            results.append(RuleTestResult(rule_id, False, "no matching rule"))
            continue

        problems: list[str] = []
        positives = _events(raw.get("true_positive"))
        negatives = _events(raw.get("true_negative"))

        if not positives:
            problems.append("no true_positive cases")
        elif not any(alert.rule_id == rule_id for alert in run_rules(positives, [rule])):
            problems.append("true_positive did not fire")

        if negatives and any(alert.rule_id == rule_id for alert in run_rules(negatives, [rule])):
            problems.append("true_negative fired")

        results.append(RuleTestResult(rule_id, not problems, "; ".join(problems) or "ok"))

    return results


def has_failures(results: list[RuleTestResult]) -> bool:
    return any(not result.passed for result in results)
