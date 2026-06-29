import pytest

from greynoc_dmz.ai import (
    AIConfig,
    AIReadinessStatus,
    AnthropicProvider,
    GoogleGeminiProvider,
    OpenAICompatibleProvider,
    build_provider,
    check_ai_readiness,
)
from greynoc_dmz.ai.models import AIProviderError


@pytest.fixture(autouse=True)
def _clean_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_build_provider_dispatches_by_provider() -> None:
    anthropic = build_provider(AIConfig(enabled=True, provider="anthropic", model="m"))
    claude = build_provider(AIConfig(enabled=True, provider="claude", model="m"))
    gemini = build_provider(AIConfig(enabled=True, provider="gemini", model="m"))
    google = build_provider(AIConfig(enabled=True, provider="google", model="m"))
    openai = build_provider(
        AIConfig(enabled=True, provider="openai_compatible", base_url="http://localhost/v1", model="m")
    )

    assert isinstance(anthropic, AnthropicProvider)
    assert isinstance(claude, AnthropicProvider)
    assert isinstance(gemini, GoogleGeminiProvider)
    assert isinstance(google, GoogleGeminiProvider)
    assert isinstance(openai, OpenAICompatibleProvider)


def test_build_provider_rejects_unknown() -> None:
    with pytest.raises(AIProviderError):
        build_provider(AIConfig(enabled=True, provider="mystery", model="m"))


def test_anthropic_uses_default_base_url() -> None:
    config = AIConfig(
        enabled=True,
        provider="anthropic",
        model="claude-opus-4-8",
        token_env="ANTHROPIC_API_KEY",
        allow_external=True,
    )
    # No base_url set: readiness resolves the hosted default, so it gets past the
    # base-url check and the only thing missing is the (unset) named key.
    readiness = check_ai_readiness(config)
    assert readiness.status == AIReadinessStatus.missing_config
    assert "BASE_URL" not in readiness.detail
    assert "ANTHROPIC_API_KEY" in readiness.detail


def test_anthropic_ready_with_key_and_external(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    config = AIConfig(
        enabled=True,
        provider="anthropic",
        model="claude-opus-4-8",
        token_env="ANTHROPIC_API_KEY",
        allow_external=True,
    )

    readiness = check_ai_readiness(config)

    assert readiness.status == AIReadinessStatus.ready
    assert readiness.external is True


def test_hosted_provider_blocked_without_external(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "goog-test")
    config = AIConfig(
        enabled=True, provider="gemini", model="gemini-2.0-flash", token_env="GEMINI_API_KEY"
    )

    readiness = check_ai_readiness(config)

    assert readiness.status == AIReadinessStatus.blocked
    assert readiness.external is True


def test_hosted_provider_requires_token_env() -> None:
    config = AIConfig(enabled=True, provider="gemini", model="m", allow_external=True)

    readiness = check_ai_readiness(config)

    assert readiness.status == AIReadinessStatus.missing_config
    assert "requires an API key" in readiness.detail


def test_missing_model_keeps_external_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "goog-test")
    config = AIConfig(
        enabled=True,
        provider="gemini",
        model=None,
        token_env="GEMINI_API_KEY",
        allow_external=True,
    )

    readiness = check_ai_readiness(config)

    assert readiness.status == AIReadinessStatus.missing_config
    assert "MODEL" in readiness.detail
    assert readiness.external is True


def test_local_openai_provider_ready_without_token() -> None:
    config = AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        model="llama3.1",
    )

    readiness = check_ai_readiness(config)

    assert readiness.status == AIReadinessStatus.ready
    assert readiness.external is False
