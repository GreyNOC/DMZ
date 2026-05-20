from pathlib import Path

from greynoc_dmz.engine import run_scenario, validate_all

ROOT = Path(__file__).resolve().parents[1]


def test_auth_scenario_passes() -> None:
    result = run_scenario(
        ROOT / "scenarios" / "auth-bruteforce-sim.json",
        ROOT / "detections" / "rules",
    )
    assert result.passed is True
    assert result.fired_rules == ["GNOC-AUTH-001"]


def test_all_scenarios_pass() -> None:
    results = validate_all(ROOT)
    assert results
    assert all(result.passed for result in results)
