"""GreyNOC DMZ AI provider layer.

A user brings their own AI provider (hosted or local) through a vendor-neutral
adapter. AI output is advisory; the core validation engine never depends on it.
"""

from __future__ import annotations

from .config import AIConfig, load_ai_config
from .models import (
    AIProvider,
    AIProviderError,
    AIReadiness,
    AIReadinessStatus,
    AIResponse,
)
from .openai_compatible import OpenAICompatibleProvider
from .review import build_review_prompt, run_scenario_review
from .service import build_provider, check_ai_readiness, run_live_check

__all__ = [
    "AIConfig",
    "AIProvider",
    "AIProviderError",
    "AIReadiness",
    "AIReadinessStatus",
    "AIResponse",
    "OpenAICompatibleProvider",
    "build_provider",
    "build_review_prompt",
    "check_ai_readiness",
    "load_ai_config",
    "run_live_check",
    "run_scenario_review",
]
