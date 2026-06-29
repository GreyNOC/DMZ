from __future__ import annotations

import os

from ..integrations.safety import EndpointScope, SafetyPolicy, check_endpoint
from . import anthropic_provider, gemini_provider
from .config import AIConfig
from .models import AIProvider, AIProviderError, AIReadiness, AIReadinessStatus, AIResponse
from .openai_compatible import OpenAICompatibleProvider

# Provider aliases the arena understands. Each maps to one adapter class below.
_OPENAI_PROVIDERS = {"openai_compatible", "openai"}
_ANTHROPIC_PROVIDERS = {"anthropic", "claude"}
_GEMINI_PROVIDERS = {"gemini", "google"}
_SUPPORTED_PROVIDERS = _OPENAI_PROVIDERS | _ANTHROPIC_PROVIDERS | _GEMINI_PROVIDERS

# Providers that always need an API key (the hosted vendors). Local OpenAI-style
# servers can run without one, so openai_compatible is intentionally excluded.
_TOKEN_REQUIRED = _ANTHROPIC_PROVIDERS | _GEMINI_PROVIDERS

# Hosted providers expose a stable default endpoint, so base_url is optional.
_PROVIDER_DEFAULT_BASE: dict[str, str] = {
    **{name: anthropic_provider.DEFAULT_BASE_URL for name in _ANTHROPIC_PROVIDERS},
    **{name: gemini_provider.DEFAULT_BASE_URL for name in _GEMINI_PROVIDERS},
}


def _effective_base_url(config: AIConfig) -> str | None:
    return config.base_url or _PROVIDER_DEFAULT_BASE.get(config.provider)


def build_provider(config: AIConfig) -> AIProvider:
    """Construct the AI provider selected by the configuration."""
    provider = config.provider
    if provider not in _SUPPORTED_PROVIDERS:
        raise AIProviderError(f"unsupported AI provider '{provider}'")
    token = os.environ.get(config.token_env) if config.token_env else None
    if provider in _ANTHROPIC_PROVIDERS:
        return anthropic_provider.AnthropicProvider(config, token)
    if provider in _GEMINI_PROVIDERS:
        return gemini_provider.GoogleGeminiProvider(config, token)
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

    base_url = _effective_base_url(config)
    if not base_url:
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            "missing GREYNOC_DMZ_AI_BASE_URL",
            False,
        )

    # Resolve the endpoint scope up front so the external flag stays accurate even
    # when configuration is incomplete (a hosted provider missing a key is still
    # external).
    verdict = check_endpoint(
        base_url, SafetyPolicy(allow_external=config.allow_external, allowlist=frozenset())
    )
    external = verdict.scope is EndpointScope.external

    if not model:
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            "missing GREYNOC_DMZ_AI_MODEL",
            external,
        )

    token_value = os.environ.get(config.token_env, "").strip() if config.token_env else ""
    if config.token_env and not token_value:
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            f"token env '{config.token_env}' is named but not set",
            external,
        )
    if provider in _TOKEN_REQUIRED and not token_value:
        return AIReadiness(
            AIReadinessStatus.missing_config,
            provider,
            model,
            f"{provider} requires an API key; name it with token_env",
            external,
        )

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
