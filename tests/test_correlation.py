from datetime import UTC, datetime, timedelta

from greynoc_dmz.correlation import correlate
from greynoc_dmz.models import Alert, TelemetryEvent


def _alert(rule_id: str, host: str, severity: str, mitre: list[str], minutes: int) -> Alert:
    first = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    last = first + timedelta(minutes=minutes)
    event = TelemetryEvent(
        timestamp=first, source="lab", host=host, event_type="process_event", message="m"
    )
    return Alert(
        rule_id=rule_id,
        rule_name=rule_id,
        severity=severity,
        host=host,
        user="alice",
        event_count=2,
        first_seen=first,
        last_seen=last,
        dwell_seconds=(last - first).total_seconds(),
        evidence=[event],
        mitre=mitre,
    )


def test_correlate_groups_alerts_by_host() -> None:
    alerts = [
        _alert("GNOC-EXEC-001", "host-a", "high", ["TA0002", "T1059.001"], 2),
        _alert("GNOC-DISC-001", "host-a", "medium", ["TA0007", "T1087.001"], 6),
        _alert("GNOC-WEB-001", "host-b", "low", ["TA0001", "T1190"], 1),
    ]

    incidents = correlate(alerts)

    assert [i.host for i in incidents] == ["host-a", "host-b"]
    host_a = incidents[0]
    assert host_a.severity.value == "high"  # max severity across the host's alerts
    assert host_a.rule_ids == ["GNOC-DISC-001", "GNOC-EXEC-001"]
    assert host_a.tactics == ["TA0002", "TA0007"]
    assert host_a.techniques == ["T1059.001", "T1087.001"]
    assert host_a.alert_count == 2
    assert host_a.event_count == 4
    assert host_a.dwell_seconds == 360.0  # 0..6 minutes


def test_correlate_orders_by_severity() -> None:
    alerts = [
        _alert("GNOC-WEB-001", "host-low", "low", ["TA0001"], 1),
        _alert("GNOC-IMP-001", "host-crit", "critical", ["TA0040"], 1),
    ]

    incidents = correlate(alerts)

    assert [i.host for i in incidents] == ["host-crit", "host-low"]


def test_correlate_empty() -> None:
    assert correlate([]) == []
