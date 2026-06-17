from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TelemetryEvent(BaseModel):
    timestamp: datetime
    source: str
    host: str
    event_type: str
    user: str | None = None
    ip: str | None = None
    message: str
    fields: dict[str, Any] = Field(default_factory=dict)


class DetectionRule(BaseModel):
    id: str
    name: str
    description: str
    severity: Severity
    data_source: str
    event_type: str | None = None
    match: dict[str, Any] = Field(default_factory=dict)
    threshold: int = 1
    window_minutes: int = 10
    mitre: list[str] = Field(default_factory=list)
    runbook: str | None = None

    @field_validator("id")
    @classmethod
    def id_must_be_stable(cls, value: str) -> str:
        if not value.startswith("GNOC-"):
            raise ValueError("rule id must start with GNOC-")
        return value


class Alert(BaseModel):
    rule_id: str
    rule_name: str
    severity: Severity
    host: str
    user: str | None = None
    event_count: int
    first_seen: datetime
    last_seen: datetime
    dwell_seconds: float
    evidence: list[TelemetryEvent]
    runbook: str | None = None
    mitre: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    name: str
    team: Literal["red", "blue", "purple"]
    description: str
    telemetry_file: Path
    expected_rules: list[str]
    notes: str | None = None


class ScenarioResult(BaseModel):
    scenario_id: str
    scenario_name: str
    passed: bool
    expected_rules: list[str]
    fired_rules: list[str]
    missing_rules: list[str]
    unexpected_rules: list[str]
    alerts: list[Alert]
