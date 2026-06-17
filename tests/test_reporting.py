from datetime import UTC, datetime

from greynoc_dmz.models import ScenarioResult
from greynoc_dmz.reporting import render_result_markdown


def _result() -> ScenarioResult:
    return ScenarioResult(
        scenario_id="demo",
        scenario_name="Demo scenario",
        passed=True,
        expected_rules=[],
        fired_rules=[],
        missing_rules=[],
        unexpected_rules=[],
        alerts=[],
    )


def test_report_is_byte_identical_with_fixed_timestamp() -> None:
    stamp = datetime(2026, 1, 1, tzinfo=UTC)

    first = render_result_markdown(_result(), stamp)
    second = render_result_markdown(_result(), stamp)

    assert first == second
    assert "2026-01-01T00:00:00+00:00" in first
