from datetime import UTC, datetime
from pathlib import Path

from greynoc_dmz.engine import run_rules, run_scenario, validate_all
from greynoc_dmz.models import DetectionRule, TelemetryEvent

ROOT = Path(__file__).resolve().parents[1]


def test_auth_scenario_passes() -> None:
    result = run_scenario(
        ROOT / "scenarios" / "auth-bruteforce-sim.json",
        ROOT / "detections" / "rules",
    )
    assert result.passed is True
    assert result.fired_rules == ["GNOC-AUTH-001"]


def test_run_scenario_resolves_telemetry_from_explicit_root() -> None:
    result = run_scenario(
        ROOT / "scenarios" / "auth-bruteforce-sim.json",
        ROOT / "detections" / "rules",
        telemetry_root=ROOT,
    )

    assert result.passed is True
    assert result.fired_rules == ["GNOC-AUTH-001"]


def test_all_scenarios_pass() -> None:
    results = validate_all(ROOT)
    assert results
    assert all(result.passed for result in results)


def test_validate_all_without_persist_writes_nothing(tmp_path: Path) -> None:
    import shutil

    for name in ("detections", "scenarios", "telemetry", "runbooks", "configs"):
        shutil.copytree(ROOT / name, tmp_path / name)

    results = validate_all(tmp_path, persist=False)

    assert results
    assert not (tmp_path / ".dmz").exists()
    assert not (tmp_path / "evidence").exists()


def test_threshold_respects_window() -> None:
    rule = DetectionRule(
        id="GNOC-TEST-001",
        name="Window test",
        description="Window regression test",
        severity="low",
        data_source="auth",
        event_type="auth_failed",
        match={"message": "failed login"},
        threshold=2,
        window_minutes=1,
    )
    events = [
        TelemetryEvent(
            timestamp=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            source="auth",
            host="range-linux-01",
            event_type="auth_failed",
            user="alice",
            message="failed login",
        ),
        TelemetryEvent(
            timestamp=datetime(2026, 5, 19, 12, 5, tzinfo=UTC),
            source="auth",
            host="range-linux-01",
            event_type="auth_failed",
            user="alice",
            message="failed login",
        ),
    ]

    assert run_rules(events, [rule]) == []
