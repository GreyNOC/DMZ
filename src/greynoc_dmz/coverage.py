from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import load_rules
from .models import DetectionRule

# Enterprise ATT&CK tactics, in catalog order. Used to label TA* ids and to
# compute coverage gaps (tactics with no detection rule mapped to them).
ATTACK_TACTICS: dict[str, str] = {
    "TA0043": "Reconnaissance",
    "TA0042": "Resource Development",
    "TA0001": "Initial Access",
    "TA0002": "Execution",
    "TA0003": "Persistence",
    "TA0004": "Privilege Escalation",
    "TA0005": "Defense Evasion",
    "TA0006": "Credential Access",
    "TA0007": "Discovery",
    "TA0008": "Lateral Movement",
    "TA0009": "Collection",
    "TA0011": "Command and Control",
    "TA0010": "Exfiltration",
    "TA0040": "Impact",
}

TACTIC_RE = re.compile(r"^TA\d{4}$")
TECHNIQUE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")


@dataclass(frozen=True)
class TacticCoverage:
    tactic_id: str
    name: str
    rule_ids: list[str]

    @property
    def covered(self) -> bool:
        return bool(self.rule_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tactic_id": self.tactic_id,
            "name": self.name,
            "covered": self.covered,
            "rule_ids": self.rule_ids,
        }


@dataclass(frozen=True)
class CoverageReport:
    tactics: list[TacticCoverage]
    techniques: dict[str, list[str]]
    unmapped_rules: list[str]

    @property
    def covered_tactics(self) -> list[TacticCoverage]:
        return [item for item in self.tactics if item.covered]

    @property
    def tactic_coverage_ratio(self) -> tuple[int, int]:
        return len(self.covered_tactics), len(self.tactics)

    def to_dict(self) -> dict[str, Any]:
        covered, total = self.tactic_coverage_ratio
        return {
            "covered_tactics": covered,
            "total_tactics": total,
            "technique_count": len(self.techniques),
            "tactics": [item.to_dict() for item in self.tactics],
            "techniques": self.techniques,
            "unmapped_rules": self.unmapped_rules,
        }


def build_coverage(rules: list[DetectionRule]) -> CoverageReport:
    tactic_rules: dict[str, list[str]] = defaultdict(list)
    technique_rules: dict[str, list[str]] = defaultdict(list)
    unmapped: list[str] = []

    for rule in rules:
        mapped = False
        for raw in rule.mitre:
            token = raw.strip().upper()
            if TACTIC_RE.match(token):
                tactic_rules[token].append(rule.id)
                mapped = True
            elif TECHNIQUE_RE.match(token):
                technique_rules[token].append(rule.id)
                mapped = True
        if not mapped:
            unmapped.append(rule.id)

    tactics = [
        TacticCoverage(tactic_id, name, sorted(set(tactic_rules.get(tactic_id, []))))
        for tactic_id, name in ATTACK_TACTICS.items()
    ]
    techniques = {key: sorted(set(value)) for key, value in sorted(technique_rules.items())}
    return CoverageReport(tactics=tactics, techniques=techniques, unmapped_rules=sorted(set(unmapped)))


def coverage_for_root(root: Path) -> CoverageReport:
    return build_coverage(load_rules(root / "detections" / "rules"))
