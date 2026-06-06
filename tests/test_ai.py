import pytest

from greynoc_dmz.ai import (
    AIConfig,
    AIReadinessStatus,
    build_review_prompt,
    check_ai_readiness,
    load_ai_config,
)
from greynoc_dmz.models import ScenarioResult

_AI_ENV_VARS = [
    "GREYNOC_DMZ_AI_ENABLED",
    "GREYNOC_DMZ_AI_PROVIDER",
    "GREYNOC_DMZ_AI_MODEL",
    "GREYNOC_DMZ_AI_BASE_URL",
    "GREYNOC_DMZ_AI_TOKEN_ENV",
    "GREYNOC_DMZ_AI_TIMEOUT_SECONDS",
    "GREYNOC_DMZ_AI_TEMPERATURE",
    "GREYNOC_DMZ_AI_ALLOW_EXTERNAL",
]


@pytest.fixture(autouse=True)
def _clean_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _AI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _result(*, passed: bool = True) -> ScenarioResult:
    return ScenarioResult(
        scenario_id="auth-bruteforce-sim",
        scenario_name="Test scenario",
        passed=passed,
        expected_rules=["GNOC-AUTH-001"],
        fired_rules=["GNOC-AUTH-001"] if passed else [],
        missing_rules=[] if passed else ["GNOC-AUTH-001"],
        unexpected_rules=[],
        alerts=[],
    )


def test_default_config_is_disabled() -> None:
    config = load_ai_config()
    assert config.enabled is False
    assert config.provider == "disabled"


def test_config_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GREYNOC_DMZ_AI_ENABLED", "true")
    monkeypatch.setenv("GREYNOC_DMZ_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GREYNOC_DMZ_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("GREYNOC_DMZ_AI_MODEL", "llama3.1")
    monkeypatch.setenv("GREYNOC_DMZ_AI_TEMPERATURE", "0.5")

    config = load_ai_config()

    assert config.enabled is True
    assert config.provider == "openai_compatible"
    assert config.base_url == "http://127.0.0.1:11434/v1"
    assert config.model == "llama3.1"
    assert config.temperature == 0.5


def test_disabled_config_reports_disabled() -> None:
    assert check_ai_readiness(AIConfig()).status == AIReadinessStatus.disabled


def test_missing_base_url_reports_missing_config() -> None:
    config = AIConfig(enabled=True, provider="openai_compatible", model="llama3.1")

    check = check_ai_readiness(config)

    assert check.status == AIReadinessStatus.missing_config
    assert "BASE_URL" in check.detail


def test_missing_model_reports_missing_config() -> None:
    config = AIConfig(
        enabled=True, provider="openai_compatible", base_url="http://127.0.0.1:11434/v1"
    )

    check = check_ai_readiness(config)

    assert check.status == AIReadinessStatus.missing_config
    assert "MODEL" in check.detail


def test_unsupported_provider_reports_missing_config() -> None:
    config = AIConfig(enabled=True, provider="mystery", base_url="http://127.0.0.1:1/v1", model="m")

    assert check_ai_readiness(config).status == AIReadinessStatus.missing_config


def test_named_token_env_must_be_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DMZ_TEST_AI_KEY", raising=False)
    config = AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        model="m",
        token_env="DMZ_TEST_AI_KEY",
    )

    check = check_ai_readiness(config)

    assert check.status == AIReadinessStatus.missing_config
    assert "DMZ_TEST_AI_KEY" in check.detail


def test_local_provider_is_ready_without_a_token() -> None:
    config = AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        model="llama3.1",
    )

    check = check_ai_readiness(config)

    assert check.status == AIReadinessStatus.ready
    assert check.external is False


def test_public_provider_blocked_without_allow_external() -> None:
    config = AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
    )

    check = check_ai_readiness(config)

    assert check.status == AIReadinessStatus.blocked
    assert check.external is True


def test_public_provider_ready_when_external_allowed() -> None:
    config = AIConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        allow_external=True,
    )

    check = check_ai_readiness(config)

    assert check.status == AIReadinessStatus.ready
    assert check.external is True


def test_review_prompt_includes_scenarios_and_marks_synthetic() -> None:
    prompt = build_review_prompt([_result(passed=True), _result(passed=False)])

    assert "synthetic" in prompt.lower()
    assert "PASS" in prompt
    assert "FAIL" in prompt
    assert "GNOC-AUTH-001" in prompt
