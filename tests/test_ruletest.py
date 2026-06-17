import json
from pathlib import Path

from greynoc_dmz.ruletest import has_failures, run_rule_tests

ROOT = Path(__file__).resolve().parents[1]


def test_repo_rule_tests_all_pass() -> None:
    results = run_rule_tests(ROOT)

    assert results
    assert not has_failures(results)
    # every shipped rule has a test case
    rule_ids = {p.stem for p in (ROOT / "detections" / "rules").glob("*.json")}
    tested_ids = {r.rule_id for r in results}
    assert rule_ids <= tested_ids


def _rule(root: Path) -> None:
    (root / "detections" / "rules").mkdir(parents=True)
    (root / "detections" / "tests").mkdir(parents=True)
    (root / "detections" / "rules" / "r.json").write_text(
        json.dumps(
            {
                "id": "GNOC-T-001",
                "name": "t",
                "description": "t",
                "severity": "low",
                "data_source": "auth",
                "event_type": "auth_failed",
                "match": {"message": "failed login"},
            }
        ),
        encoding="utf-8",
    )


def _event(message: str) -> dict[str, object]:
    return {
        "timestamp": "2026-05-20T12:00:00Z",
        "source": "auth",
        "host": "h",
        "event_type": "auth_failed",
        "user": "alice",
        "message": message,
        "fields": {},
    }


def test_runner_detects_true_positive_that_fails_to_fire(tmp_path: Path) -> None:
    _rule(tmp_path)
    (tmp_path / "detections" / "tests" / "GNOC-T-001.json").write_text(
        json.dumps({"rule_id": "GNOC-T-001", "true_positive": [_event("nothing here")]}),
        encoding="utf-8",
    )

    results = run_rule_tests(tmp_path)

    assert has_failures(results)
    assert results[0].detail == "true_positive did not fire"


def test_runner_detects_true_negative_that_fires(tmp_path: Path) -> None:
    _rule(tmp_path)
    (tmp_path / "detections" / "tests" / "GNOC-T-001.json").write_text(
        json.dumps(
            {
                "rule_id": "GNOC-T-001",
                "true_positive": [_event("failed login for alice")],
                "true_negative": [_event("failed login again")],
            }
        ),
        encoding="utf-8",
    )

    results = run_rule_tests(tmp_path)

    assert has_failures(results)
    assert "true_negative fired" in results[0].detail
