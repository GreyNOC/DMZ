from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .io import read_json
from .models import DetectionRule, Scenario

ERROR = "error"
WARNING = "warning"

# A MITRE id is either a tactic (TA####) or a technique/sub-technique (T####[.###]).
MITRE_RE = re.compile(r"^(TA\d{4}|T\d{4}(\.\d{3})?)$")


@dataclass(frozen=True)
class LintFinding:
    target: str
    level: str
    message: str


def _lint_rules(root: Path, findings: list[LintFinding]) -> set[str]:
    rule_dir = root / "detections" / "rules"
    seen: dict[str, str] = {}
    valid_ids: set[str] = set()

    for path in sorted(rule_dir.glob("*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            rule = DetectionRule.model_validate(read_json(path))
        except ValidationError as exc:
            findings.append(LintFinding(rel, ERROR, f"invalid rule: {exc.error_count()} error(s)"))
            continue

        valid_ids.add(rule.id)
        if rule.id in seen:
            findings.append(
                LintFinding(rule.id, ERROR, f"duplicate rule id (also in {seen[rule.id]})")
            )
        seen[rule.id] = rel

        if not rule.mitre:
            findings.append(LintFinding(rule.id, WARNING, "no MITRE ATT&CK mapping"))
        for token in rule.mitre:
            if not MITRE_RE.fullmatch(token.strip().upper()):
                findings.append(LintFinding(rule.id, ERROR, f"malformed MITRE id: {token!r}"))

        if rule.runbook and not (root / rule.runbook).exists():
            findings.append(LintFinding(rule.id, ERROR, f"runbook not found: {rule.runbook}"))
        if not rule.runbook:
            findings.append(LintFinding(rule.id, WARNING, "no runbook linked"))
        if rule.threshold < 1:
            findings.append(LintFinding(rule.id, ERROR, "threshold must be >= 1"))
        if rule.window_minutes < 1:
            findings.append(LintFinding(rule.id, ERROR, "window_minutes must be >= 1"))

    return valid_ids


def _lint_scenarios(root: Path, valid_ids: set[str], findings: list[LintFinding]) -> None:
    for path in sorted((root / "scenarios").glob("*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            scenario = Scenario.model_validate(read_json(path))
        except ValidationError as exc:
            findings.append(LintFinding(rel, ERROR, f"invalid scenario: {exc.error_count()} error(s)"))
            continue

        if not scenario.expected_rules:
            findings.append(LintFinding(scenario.id, WARNING, "no expected_rules declared"))
        for rule_id in scenario.expected_rules:
            if rule_id not in valid_ids:
                findings.append(
                    LintFinding(scenario.id, ERROR, f"expects unknown rule {rule_id}")
                )
        if not (root / scenario.telemetry_file).exists():
            findings.append(
                LintFinding(scenario.id, ERROR, f"telemetry not found: {scenario.telemetry_file}")
            )


def lint_repo(root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    valid_ids = _lint_rules(root, findings)
    _lint_scenarios(root, valid_ids, findings)
    return findings


def has_errors(findings: list[LintFinding]) -> bool:
    return any(finding.level == ERROR for finding in findings)
