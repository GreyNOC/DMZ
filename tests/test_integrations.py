import json
from pathlib import Path

from greynoc_dmz.integrations import (
    IntegrationConfig,
    IntegrationKind,
    IntegrationStatus,
    adapter_names,
    check_integration_config,
    default_integrations,
    load_integrations,
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


def test_builtin_adapters_are_registered() -> None:
    assert {"file", "webhook", "splunk_hec", "jira"} <= set(adapter_names())


def test_file_adapter_is_ready_without_an_endpoint() -> None:
    config = IntegrationConfig(
        name="local-file",
        kind=IntegrationKind.file,
        adapter="file",
        enabled=True,
    )

    assert check_integration_config(config).status == IntegrationStatus.ready


def test_unknown_adapter_reports_missing_config() -> None:
    config = IntegrationConfig(
        name="mystery",
        kind=IntegrationKind.siem,
        adapter="does-not-exist",
        enabled=True,
    )

    check = check_integration_config(config)

    assert check.status == IntegrationStatus.missing_config
    assert "unknown adapter" in check.detail


def test_jira_adapter_requires_options() -> None:
    config = IntegrationConfig(
        name="jira",
        kind=IntegrationKind.ticketing,
        adapter="jira",
        enabled=True,
        base_url="https://example.invalid",
        token_env="DMZ_JIRA_API_TOKEN",
    )

    check = check_integration_config(config)

    assert check.status == IntegrationStatus.missing_config
    assert check.detail == "missing options.email"


def test_load_integrations_falls_back_to_defaults(tmp_path: Path) -> None:
    assert load_integrations(tmp_path) == default_integrations()


def test_load_integrations_reads_config_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "integrations.json").write_text(
        json.dumps(
            {
                "integrations": [
                    {
                        "name": "lab-splunk",
                        "kind": "siem",
                        "adapter": "splunk_hec",
                        "enabled": True,
                        "base_url": "https://splunk.example.invalid:8088",
                        "token_env": "DMZ_SPLUNK_HEC_TOKEN",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    configs = load_integrations(tmp_path)

    assert len(configs) == 1
    assert configs[0].name == "lab-splunk"
    assert configs[0].adapter == "splunk_hec"
    assert configs[0].enabled is True
