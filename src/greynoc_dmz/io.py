from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from .models import DetectionRule, Scenario, TelemetryEvent

T = TypeVar("T", bound=BaseModel)


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, default=str)
        handle.write("\n")


def load_rules(rule_dir: Path) -> list[DetectionRule]:
    files = sorted(rule_dir.glob("*.json"))
    adapter = TypeAdapter(DetectionRule)
    return [adapter.validate_python(read_json(path)) for path in files]


def load_scenario(path: Path) -> Scenario:
    return Scenario.model_validate(read_json(path))


def load_events(path: Path) -> list[TelemetryEvent]:
    adapter = TypeAdapter(list[TelemetryEvent])
    return adapter.validate_python(read_json(path))
