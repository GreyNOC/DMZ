import json
from pathlib import Path

from greynoc_dmz.lint import has_errors, lint_repo

ROOT = Path(__file__).resolve().parents[1]


def test_repo_lint_is_clean() -> None:
    findings = lint_repo(ROOT)

    assert not has_errors(findings)


def _write_rule(path: Path, **overrides: object) -> None:
    rule: dict[str, object] = {
        "id": "GNOC-TEST-001",
        "name": "Test rule",
        "description": "test",
        "severity": "low",
        "data_source": "auth",
        "mitre": ["TA0006"],
    }
    rule.update(overrides)
    path.write_text(json.dumps(rule), encoding="utf-8")


def _lab(root: Path) -> Path:
    (root / "detections" / "rules").mkdir(parents=True)
    (root / "scenarios").mkdir()
    return root


def test_lint_flags_missing_runbook(tmp_path: Path) -> None:
    root = _lab(tmp_path)
    _write_rule(root / "detections" / "rules" / "r.json", runbook="runbooks/does-not-exist.md")

    findings = lint_repo(root)

    assert has_errors(findings)
    assert any("runbook not found" in f.message for f in findings)


def test_lint_flags_scenario_referencing_unknown_rule(tmp_path: Path) -> None:
    root = _lab(tmp_path)
    _write_rule(root / "detections" / "rules" / "r.json")
    (root / "telemetry").mkdir()
    (root / "telemetry" / "t.json").write_text("[]", encoding="utf-8")
    (root / "scenarios" / "s.json").write_text(
        json.dumps(
            {
                "id": "s",
                "name": "s",
                "team": "blue",
                "description": "d",
                "telemetry_file": "telemetry/t.json",
                "expected_rules": ["GNOC-NOPE-001"],
            }
        ),
        encoding="utf-8",
    )

    findings = lint_repo(root)

    assert any("unknown rule" in f.message for f in findings)
