from greynoc_dmz.integrations import (
    IntegrationConfig,
    IntegrationKind,
    IntegrationStatus,
    check_integration_config,
    default_integrations,
)


def test_default_integrations_are_disabled() -> None:
    checks = [check_integration_config(item) for item in default_integrations()]

    assert checks
    assert all(item.status == IntegrationStatus.disabled for item in checks)


def test_enabled_integration_requires_base_url() -> None:
    config = IntegrationConfig(
        name="test-siem",
        kind=IntegrationKind.siem,
        enabled=True,
        token_env="DMZ_CREDENTIAL_REFERENCE",
    )

    check = check_integration_config(config)

    assert check.status == IntegrationStatus.missing_config
    assert check.detail == "missing base_url"


def test_enabled_integration_requires_credential_reference() -> None:
    config = IntegrationConfig(
        name="test-ticketing",
        kind=IntegrationKind.ticketing,
        enabled=True,
        base_url="https://example.invalid",
    )

    check = check_integration_config(config)

    assert check.status == IntegrationStatus.missing_config
    assert check.detail == "missing token_env"


def test_ready_integration() -> None:
    config = IntegrationConfig(
        name="test-cloud",
        kind=IntegrationKind.cloud,
        enabled=True,
        base_url="https://example.invalid",
        token_env="DMZ_CREDENTIAL_REFERENCE",
    )

    check = check_integration_config(config)

    assert check.status == IntegrationStatus.ready
