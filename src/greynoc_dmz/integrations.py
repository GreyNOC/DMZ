from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .models import Alert, ScenarioResult


class IntegrationKind(StrEnum):
    siem = "siem"
    edr = "edr"
    ticketing = "ticketing"
    cloud = "cloud"


class IntegrationStatus(StrEnum):
    ready = "ready"
    disabled = "disabled"
    missing_config = "missing_config"


@dataclass(frozen=True)
class IntegrationConfig:
    name: str
    kind: IntegrationKind
    enabled: bool = False
    base_url: str | None = None
    token_env: str | None = None
    timeout_seconds: int = 10


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    kind: IntegrationKind
    status: IntegrationStatus
    detail: str


class AlertSink(Protocol):
    def send_alert(self, alert: Alert) -> str:
        """Send one alert and return the remote identifier."""


class ScenarioPublisher(Protocol):
    def publish_result(self, result: ScenarioResult) -> str:
        """Publish one scenario result and return the remote identifier."""


def check_integration_config(config: IntegrationConfig) -> IntegrationCheck:
    if not config.enabled:
        return IntegrationCheck(
            name=config.name,
            kind=config.kind,
            status=IntegrationStatus.disabled,
            detail="integration disabled",
        )
    if not config.base_url:
        return IntegrationCheck(
            name=config.name,
            kind=config.kind,
            status=IntegrationStatus.missing_config,
            detail="missing base_url",
        )
    if not config.token_env:
        return IntegrationCheck(
            name=config.name,
            kind=config.kind,
            status=IntegrationStatus.missing_config,
            detail="missing token_env",
        )
    return IntegrationCheck(
        name=config.name,
        kind=config.kind,
        status=IntegrationStatus.ready,
        detail="configuration present",
    )


def default_integrations() -> list[IntegrationConfig]:
    return [
        IntegrationConfig(name="generic-siem", kind=IntegrationKind.siem),
        IntegrationConfig(name="generic-edr", kind=IntegrationKind.edr),
        IntegrationConfig(name="generic-ticketing", kind=IntegrationKind.ticketing),
        IntegrationConfig(name="generic-cloud", kind=IntegrationKind.cloud),
    ]
