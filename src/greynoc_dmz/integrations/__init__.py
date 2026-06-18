"""GreyNOC DMZ outbound integration layer.

Detection-validation results are published to existing security tooling
(SIEM, EDR, ticketing, MSP dashboards) through small vendor-neutral adapters.
The core engine never imports a vendor SDK.
"""

from __future__ import annotations

from . import adapters  # noqa: F401  -- imported so built-in adapters self-register
from .config import (
    CONFIG_RELATIVE_PATH,
    check_integration_config,
    default_integrations,
    load_integrations,
)
from .dispatch import build_adapter, publish_all, publish_result
from .models import (
    Adapter,
    IntegrationCheck,
    IntegrationConfig,
    IntegrationKind,
    IntegrationResult,
    IntegrationStatus,
    PublishContext,
    PublishOutcome,
)
from .registry import adapter_names, get_adapter, register
from .safety import (
    EndpointScope,
    EndpointVerdict,
    SafetyPolicy,
    check_endpoint,
    classify_host,
    load_safety_policy,
)

__all__ = [
    "CONFIG_RELATIVE_PATH",
    "Adapter",
    "EndpointScope",
    "EndpointVerdict",
    "IntegrationCheck",
    "IntegrationConfig",
    "IntegrationKind",
    "IntegrationResult",
    "IntegrationStatus",
    "PublishContext",
    "PublishOutcome",
    "SafetyPolicy",
    "adapter_names",
    "build_adapter",
    "check_endpoint",
    "check_integration_config",
    "classify_host",
    "default_integrations",
    "get_adapter",
    "load_integrations",
    "load_safety_policy",
    "publish_all",
    "publish_result",
    "register",
]
