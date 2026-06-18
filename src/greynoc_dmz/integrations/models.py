from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from ..models import ScenarioResult


class IntegrationKind(StrEnum):
    siem = "siem"
    edr = "edr"
    ticketing = "ticketing"
    cloud = "cloud"
    file = "file"


class IntegrationStatus(StrEnum):
    ready = "ready"
    disabled = "disabled"
    missing_config = "missing_config"


class PublishOutcome(StrEnum):
    sent = "sent"
    skipped = "skipped"
    dry_run = "dry_run"
    blocked = "blocked"
    error = "error"


@dataclass(frozen=True)
class IntegrationConfig:
    """One configured outbound integration.

    Credentials are never stored here. ``token_env`` holds the name of the
    environment variable that carries the secret; the value is read at runtime.
    """

    name: str
    kind: IntegrationKind
    adapter: str = "webhook"
    enabled: bool = False
    base_url: str | None = None
    token_env: str | None = None
    timeout_seconds: int = 10
    verify_tls: bool = True
    options: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    kind: IntegrationKind
    adapter: str
    status: IntegrationStatus
    detail: str


@dataclass(frozen=True)
class IntegrationResult:
    """Outcome of one publish attempt for one scenario through one integration."""

    integration: str
    adapter: str
    scenario_id: str
    outcome: PublishOutcome
    target: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.outcome in {
            PublishOutcome.sent,
            PublishOutcome.skipped,
            PublishOutcome.dry_run,
        }


@dataclass(frozen=True)
class PublishContext:
    """Everything an adapter needs to publish, with the secret already resolved."""

    config: IntegrationConfig
    token: str | None
    dry_run: bool
    root: Path


class Adapter(ABC):
    """Base class for outbound integration adapters.

    Adapters are stateless. All per-call data arrives through ``PublishContext``.
    ``requires`` lists the ``IntegrationConfig`` field names that must be present
    before an enabled integration is considered ready.
    """

    name: ClassVar[str]
    requires: ClassVar[tuple[str, ...]] = ()
    required_options: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def publish_result(self, result: ScenarioResult, ctx: PublishContext) -> IntegrationResult:
        """Publish one scenario result and return what happened."""
