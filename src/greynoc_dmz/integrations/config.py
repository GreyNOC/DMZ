from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    IntegrationCheck,
    IntegrationConfig,
    IntegrationKind,
    IntegrationStatus,
)
from .registry import adapter_names, get_adapter

CONFIG_RELATIVE_PATH = Path("configs") / "integrations.json"


def default_integrations() -> list[IntegrationConfig]:
    """Built-in placeholder integrations. All disabled until configured."""
    return [
        IntegrationConfig(name="local-evidence-file", kind=IntegrationKind.file, adapter="file"),
        IntegrationConfig(name="generic-webhook", kind=IntegrationKind.edr, adapter="webhook"),
        IntegrationConfig(name="splunk-hec", kind=IntegrationKind.siem, adapter="splunk_hec"),
        IntegrationConfig(name="jira-ticketing", kind=IntegrationKind.ticketing, adapter="jira"),
    ]


def load_integrations(root: Path) -> list[IntegrationConfig]:
    """Load integrations from configs/integrations.json, or built-in defaults.

    The config file references credentials only by environment-variable name.
    It never holds secrets, so it is safe to commit.
    """
    path = root / CONFIG_RELATIVE_PATH
    if not path.exists():
        return default_integrations()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("integrations"), list):
        return default_integrations()
    return [_parse_config(entry) for entry in raw["integrations"]]


def check_integration_config(config: IntegrationConfig) -> IntegrationCheck:
    """Report whether an integration is disabled, missing config, or ready."""
    if not config.enabled:
        return _check(config, IntegrationStatus.disabled, "integration disabled")

    adapter_cls = get_adapter(config.adapter)
    if adapter_cls is None:
        known = ", ".join(adapter_names()) or "none"
        return _check(
            config,
            IntegrationStatus.missing_config,
            f"unknown adapter '{config.adapter}'; known: {known}",
        )

    for requirement in adapter_cls.requires:
        if not getattr(config, requirement, None):
            return _check(config, IntegrationStatus.missing_config, f"missing {requirement}")
    for option in adapter_cls.required_options:
        if not config.options.get(option):
            return _check(config, IntegrationStatus.missing_config, f"missing options.{option}")

    return _check(config, IntegrationStatus.ready, "configuration present")


def _check(
    config: IntegrationConfig, status: IntegrationStatus, detail: str
) -> IntegrationCheck:
    return IntegrationCheck(
        name=config.name,
        kind=config.kind,
        adapter=config.adapter,
        status=status,
        detail=detail,
    )


def _parse_config(entry: Any) -> IntegrationConfig:
    if not isinstance(entry, dict):
        raise ValueError("each integration entry must be a JSON object")
    options: dict[str, str] = {}
    raw_options = entry.get("options")
    if isinstance(raw_options, dict):
        options = {str(key): str(value) for key, value in raw_options.items()}
    return IntegrationConfig(
        name=_as_str(entry.get("name")) or "unnamed-integration",
        kind=IntegrationKind(_as_str(entry.get("kind")) or "siem"),
        adapter=_as_str(entry.get("adapter")) or "webhook",
        enabled=bool(entry.get("enabled", False)),
        base_url=_as_str(entry.get("base_url")),
        token_env=_as_str(entry.get("token_env")),
        timeout_seconds=_as_int(entry.get("timeout_seconds"), 10),
        verify_tls=bool(entry.get("verify_tls", True)),
        options=options,
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
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return default
