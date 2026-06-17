from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .coverage import TACTIC_RE
from .models import Alert, Severity

_SEVERITY_RANK = {
    Severity.low: 0,
    Severity.medium: 1,
    Severity.high: 2,
    Severity.critical: 3,
}


@dataclass(frozen=True)
class Incident:
    """Alerts on one host, correlated into a single incident view."""

    host: str
    severity: Severity
    rule_ids: list[str]
    tactics: list[str]
    techniques: list[str]
    alert_count: int
    event_count: int
    first_seen: datetime
    last_seen: datetime

    @property
    def dwell_seconds(self) -> float:
        return (self.last_seen - self.first_seen).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "severity": self.severity.value,
            "rule_ids": self.rule_ids,
            "tactics": self.tactics,
            "techniques": self.techniques,
            "alert_count": self.alert_count,
            "event_count": self.event_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "dwell_seconds": self.dwell_seconds,
        }


def correlate(alerts: list[Alert]) -> list[Incident]:
    by_host: dict[str, list[Alert]] = defaultdict(list)
    for alert in alerts:
        by_host[alert.host].append(alert)

    incidents: list[Incident] = []
    for host, group in by_host.items():
        mitre = sorted({token for alert in group for token in alert.mitre})
        incidents.append(
            Incident(
                host=host,
                severity=max((alert.severity for alert in group), key=lambda s: _SEVERITY_RANK[s]),
                rule_ids=sorted({alert.rule_id for alert in group}),
                tactics=[token for token in mitre if TACTIC_RE.match(token.upper())],
                techniques=[token for token in mitre if not TACTIC_RE.match(token.upper())],
                alert_count=len(group),
                event_count=sum(alert.event_count for alert in group),
                first_seen=min(alert.first_seen for alert in group),
                last_seen=max(alert.last_seen for alert in group),
            )
        )

    return sorted(incidents, key=lambda incident: (-_SEVERITY_RANK[incident.severity], incident.host))
