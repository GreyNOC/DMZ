from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class AIProviderError(RuntimeError):
    """Raised when an AI provider call fails.

    The message never contains the API key or request headers.
    """


@dataclass(frozen=True)
class AIResponse:
    provider: str
    model: str
    text: str


class AIProvider(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        """Return an advisory AI response for a DMZ workflow."""


class AIReadinessStatus(StrEnum):
    disabled = "disabled"
    missing_config = "missing_config"
    blocked = "blocked"
    ready = "ready"


@dataclass(frozen=True)
class AIReadiness:
    """Result of inspecting AI configuration without calling the provider."""

    status: AIReadinessStatus
    provider: str
    model: str | None
    detail: str
    external: bool
