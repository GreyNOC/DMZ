from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AIConfig
from .models import AIProvider, AIReadiness
from .service import build_provider, check_ai_readiness

ROSTER_RELATIVE_PATH = Path("configs") / "ai-roster.json"


@dataclass(frozen=True)
class Fighter:
    """One named AI combatant the arena can field.

    A fighter is just a provider configuration with a name. The API key is never
    stored here — ``token_env`` names the environment variable that holds it, so
    a roster file is safe to commit.
    """

    name: str
    provider: str
    model: str
    base_url: str | None = None
    token_env: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout_seconds: int = 30
    allow_external: bool = False

    def to_config(self, allow_external: bool = False) -> AIConfig:
        """Build the provider config for this fighter.

        ``allow_external`` is OR-ed in so a battle-wide flag can lift the
        isolation gate without editing the roster file.
        """
        return AIConfig(
            enabled=True,
            provider=self.provider,
            model=self.model,
            base_url=self.base_url,
            token_env=self.token_env,
            timeout_seconds=self.timeout_seconds,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            allow_external=self.allow_external or allow_external,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "token_env": self.token_env,
            "allow_external": self.allow_external,
        }


def load_roster(path: Path) -> list[Fighter]:
    """Load the fighter roster from a JSON file.

    Returns an empty list when the file is missing or malformed — there are no
    built-in fighters, because every fighter needs a real provider and key.
    """
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("fighters"), list):
        return []
    return [_parse_fighter(entry) for entry in raw["fighters"]]


def find_fighter(roster: list[Fighter], name: str) -> Fighter | None:
    key = name.strip().lower()
    return next((fighter for fighter in roster if fighter.name.lower() == key), None)


def build_fighter_provider(fighter: Fighter, allow_external: bool = False) -> AIProvider:
    return build_provider(fighter.to_config(allow_external))


def check_fighter_readiness(fighter: Fighter, allow_external: bool = False) -> AIReadiness:
    return check_ai_readiness(fighter.to_config(allow_external))


def _parse_fighter(entry: Any) -> Fighter:
    if not isinstance(entry, dict):
        raise ValueError("each fighter entry must be a JSON object")
    return Fighter(
        name=_as_str(entry.get("name")) or "unnamed-fighter",
        provider=_as_str(entry.get("provider")) or "openai_compatible",
        model=_as_str(entry.get("model")) or "",
        base_url=_as_str(entry.get("base_url")),
        token_env=_as_str(entry.get("token_env")),
        temperature=_as_float(entry.get("temperature"), 0.2),
        max_tokens=_as_int(entry.get("max_tokens"), 1024),
        timeout_seconds=_as_int(entry.get("timeout_seconds"), 30),
        allow_external=bool(entry.get("allow_external", False)),
    )


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default
