"""GreyNOC DMZ AI provider layer.

A user brings their own AI providers (hosted or local) through vendor-neutral
adapters — OpenAI-compatible, Anthropic, and Google Gemini. Providers can be
fielded individually for advisory review or registered as a roster of named
fighters for the live battle arena. AI output is advisory; the core validation
engine never depends on it.
"""

from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .config import AIConfig, load_ai_config
from .gemini_provider import GoogleGeminiProvider
from .models import (
    AIProvider,
    AIProviderError,
    AIReadiness,
    AIReadinessStatus,
    AIResponse,
)
from .openai_compatible import OpenAICompatibleProvider
from .review import build_review_prompt, run_scenario_review
from .roster import (
    Fighter,
    build_fighter_provider,
    check_fighter_readiness,
    find_fighter,
    load_roster,
)
from .service import build_provider, check_ai_readiness, run_live_check

__all__ = [
    "AIConfig",
    "AIProvider",
    "AIProviderError",
    "AIReadiness",
    "AIReadinessStatus",
    "AIResponse",
    "AnthropicProvider",
    "Fighter",
    "GoogleGeminiProvider",
    "OpenAICompatibleProvider",
    "build_fighter_provider",
    "build_provider",
    "build_review_prompt",
    "check_ai_readiness",
    "check_fighter_readiness",
    "find_fighter",
    "load_roster",
    "load_ai_config",
    "run_live_check",
    "run_scenario_review",
]
