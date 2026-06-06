from __future__ import annotations

import os

from ..integrations.safety import EndpointScope, SafetyPolicy, check_endpoint
from .config import AIConfig
from .models import AIProvider, AIProviderError, AIReadiness, AIReadinessStatus, AIResponse
from .openai_compatible import OpenAICompatibleProvider

_SUPPORTED_PROVIDERS = {"openai_compatible", "openai"}


def build_provider(config: AIConfig) -> AIProvider:
    """Construct the AI provider selected by the configuration."""
    if config.provider not in _SUPPORTED_PROVIDERS:
        raise AIProviderError(f"unsupported AI provider '{config.provider}'")
    token = os.environ.get(config.token_env) if config.token_env else None
    return OpenAICompatibleProvider(config, token)


def check_ai_readiness(config: AIConfig) -> AIReadiness:
    """Report AI readiness without contacting the provider."""
    provider = config.provider
    model = config.model

    if not config.enabled:
        return AIReadiness(AIReadinessStatus.disabled, provider, model, "AI is disabled", False)

    if provider not in _SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(_SUPPORTED_PROVIDERS))
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            f"unsupported provider; supported: {supported}",
            False,
        )
    if not config.base_url:
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            "missing GREYNOC_DMZ_AI_BASE_URL",
            False,
        )
    if not model:
        return AIReadiness(
            AIReadinessStatus.missing_config, provider, model, "missing GREYNOC_DMZ_AI_MODEL", False
        )
    if config.token_env and not os.environ.get(config.token_env, "").strip():
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            f"token env '{config.token_env}' is named but not set",
            False,
        )

    verdict = check_endpoint(
        config.base_url, SafetyPolicy(allow_external=config.allow_external, allowlist=frozenset())
    )
    external = verdict.scope is EndpointScope.external
    if not verdict.allowed:
        return AIReadiness(AIReadinessStatus.blocked, provider, model, verdict.reason, external)
    return AIReadiness(
        AIReadinessStatus.ready,
        provider,
        model,
        f"{verdict.scope.value} provider endpoint",
        external,
    )


def run_live_check(config: AIConfig) -> AIResponse:
    """Make one live provider call to confirm connectivity."""
    return build_provider(config).complete(
        "Reply with the single word: ready",
        system="You are a connectivity probe for a detection lab. Reply with one word.",
    )
