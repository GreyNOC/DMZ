from __future__ import annotations

import os
from pathlib import Path

from ..models import ScenarioResult
from .config import check_integration_config
from .models import (
    Adapter,
    IntegrationConfig,
    IntegrationResult,
    IntegrationStatus,
    PublishContext,
    PublishOutcome,
)
from .registry import get_adapter
from .safety import SafetyPolicy, check_endpoint, load_safety_policy


def build_adapter(config: IntegrationConfig) -> Adapter:
    adapter_cls = get_adapter(config.adapter)
    if adapter_cls is None:
        raise ValueError(f"unknown adapter '{config.adapter}'")
    return adapter_cls()


def publish_result(
    result: ScenarioResult,
    config: IntegrationConfig,
    *,
    dry_run: bool,
    root: Path,
    policy: SafetyPolicy,
) -> IntegrationResult:
    """Publish one scenario result through one integration.

    The endpoint safety gate runs before any adapter code, and an adapter
    failure is captured as an error result rather than crashing the run.
    """
    target = config.base_url or config.adapter
    if config.base_url:
        verdict = check_endpoint(config.base_url, policy)
        if not verdict.allowed:
            return IntegrationResult(
                integration=config.name,
                adapter=config.adapter,
                scenario_id=result.scenario_id,
                outcome=PublishOutcome.blocked,
                target=verdict.host or target,
                detail=verdict.reason,
            )

    token = os.environ.get(config.token_env) if config.token_env else None
    ctx = PublishContext(config=config, token=token, dry_run=dry_run, root=root)
    try:
        return build_adapter(config).publish_result(result, ctx)
    except Exception as error:  # an adapter must never crash a validation run
        return IntegrationResult(
            integration=config.name,
            adapter=config.adapter,
            scenario_id=result.scenario_id,
            outcome=PublishOutcome.error,
            target=target,
            detail=f"adapter error: {error}",
        )


def publish_all(
    results: list[ScenarioResult],
    configs: list[IntegrationConfig],
    *,
    dry_run: bool,
    root: Path,
    policy: SafetyPolicy | None = None,
) -> list[IntegrationResult]:
    """Publish every result through every ready integration.

    Disabled and misconfigured integrations are skipped; ``integration-check``
    reports why.
    """
    active_policy = policy or load_safety_policy()
    outcomes: list[IntegrationResult] = []
    for config in configs:
        if check_integration_config(config).status is not IntegrationStatus.ready:
            continue
        for result in results:
            outcomes.append(
                publish_result(result, config, dry_run=dry_run, root=root, policy=active_policy)
            )
    return outcomes
