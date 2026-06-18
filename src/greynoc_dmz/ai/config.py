from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AIConfig:
    """User-selected AI provider settings.

    The API key is never stored here. ``token_env`` holds the name of the
    environment variable that carries the key; the value is read at call time.
    """

    enabled: bool = False
    provider: str = "disabled"
    model: str | None = None
    base_url: str | None = None
    token_env: str | None = None
    timeout_seconds: int = 30
    temperature: float = 0.2
    allow_external: bool = False


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _opt(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw)
    except ValueError:
        return default


def load_ai_config() -> AIConfig:
    """Build the AI configuration from environment variables.

    AI is disabled unless ``GREYNOC_DMZ_AI_ENABLED`` is truthy.
    """
    return AIConfig(
        enabled=_flag("GREYNOC_DMZ_AI_ENABLED"),
        provider=_opt("GREYNOC_DMZ_AI_PROVIDER") or "disabled",
        model=_opt("GREYNOC_DMZ_AI_MODEL"),
        base_url=_opt("GREYNOC_DMZ_AI_BASE_URL"),
        token_env=_opt("GREYNOC_DMZ_AI_TOKEN_ENV"),
        timeout_seconds=_int_env("GREYNOC_DMZ_AI_TIMEOUT_SECONDS", 30),
        temperature=_float_env("GREYNOC_DMZ_AI_TEMPERATURE", 0.2),
        allow_external=_flag("GREYNOC_DMZ_AI_ALLOW_EXTERNAL"),
    )
