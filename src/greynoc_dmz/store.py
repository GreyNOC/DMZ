from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import ScenarioResult


def append_history(history_dir: Path, result: ScenarioResult) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / "scenario-history.ndjson"
    record: dict[str, Any] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "scenario_id": result.scenario_id,
        "scenario_name": result.scenario_name,
        "passed": result.passed,
        "expected_rules": result.expected_rules,
        "fired_rules": result.fired_rules,
        "missing_rules": result.missing_rules,
        "unexpected_rules": result.unexpected_rules,
        "alert_count": len(result.alerts),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")
    return path


def read_history(history_dir: Path, limit: int = 25) -> list[dict[str, Any]]:
    path = history_dir / "scenario-history.ndjson"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows[-limit:]
