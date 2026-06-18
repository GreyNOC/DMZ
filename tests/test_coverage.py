from pathlib import Path

from greynoc_dmz.coverage import build_coverage, coverage_for_root
from greynoc_dmz.models import DetectionRule

ROOT = Path(__file__).resolve().parents[1]


def _rule(rule_id: str, mitre: list[str]) -> DetectionRule:
    return DetectionRule(
        id=rule_id,
        name=rule_id,
        description="test",
        severity="low",
        data_source="auth",
        mitre=mitre,
    )


def test_build_coverage_maps_tactics_and_techniques() -> None:
    report = build_coverage([_rule("GNOC-A-001", ["TA0006", "T1110"])])

    credential_access = next(t for t in report.tactics if t.tactic_id == "TA0006")
    assert credential_access.covered is True
    assert credential_access.rule_ids == ["GNOC-A-001"]
    assert report.techniques == {"T1110": ["GNOC-A-001"]}
    assert report.tactic_coverage_ratio[0] == 1


def test_build_coverage_flags_unmapped_rules() -> None:
    report = build_coverage([_rule("GNOC-B-001", [])])

    assert report.unmapped_rules == ["GNOC-B-001"]
    assert report.tactic_coverage_ratio[0] == 0


def test_repo_coverage_has_credential_access() -> None:
    report = coverage_for_root(ROOT)

    covered_ids = {t.tactic_id for t in report.covered_tactics}
    assert "TA0006" in covered_ids
    assert report.unmapped_rules == []
