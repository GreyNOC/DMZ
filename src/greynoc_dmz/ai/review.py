from __future__ import annotations

from ..models import ScenarioResult
from .config import AIConfig
from .models import AIResponse
from .service import build_provider

_REVIEW_SYSTEM = (
    "You are a detection-engineering assistant for the GreyNOC DMZ validation lab. "
    "The input is synthetic lab data. Your output is advisory only: do not produce "
    "commands for automatic execution and do not claim to have changed any detection rule."
)


def build_review_prompt(results: list[ScenarioResult]) -> str:
    """Build an advisory-review prompt from scenario validation results."""
    lines = ["GreyNOC DMZ detection-validation results (synthetic lab data):", ""]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- {result.scenario_id} ({result.scenario_name}): {status}")
        lines.append(f"  expected rules: {', '.join(result.expected_rules) or 'none'}")
        lines.append(f"  fired rules:    {', '.join(result.fired_rules) or 'none'}")
        lines.append(f"  missing rules:  {', '.join(result.missing_rules) or 'none'}")
        lines.append(f"  unexpected:     {', '.join(result.unexpected_rules) or 'none'}")
    lines.append("")
    lines.append(
        "Summarize detection coverage, call out the most important gaps, and suggest "
        "where to focus rule tuning. Keep the response concise."
    )
    return "\n".join(lines)


def run_scenario_review(config: AIConfig, results: list[ScenarioResult]) -> AIResponse:
    """Ask the configured AI provider for an advisory review of validation results."""
    provider = build_provider(config)
    return provider.complete(build_review_prompt(results), system=_REVIEW_SYSTEM)
