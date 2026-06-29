from __future__ import annotations

import json

from .config import AIConfig
from .http import ensure_endpoint_allowed, post_and_read
from .models import AIProviderError, AIResponse

DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    """AI provider for Anthropic's native Messages API (``/v1/messages``).

    Authenticates with the ``x-api-key`` header. ``temperature`` is deliberately
    omitted so the adapter works across every current Claude model — the latest
    models reject sampling parameters, and omitting it is valid everywhere.
    """

    name = "anthropic"

    def __init__(self, config: AIConfig, token: str | None) -> None:
        self._config = config
        self._token = token

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        config = self._config
        base = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
        if not config.model:
            raise AIProviderError("AI model is not configured")
        if not self._token:
            raise AIProviderError("Anthropic provider requires an API key")
        model = config.model

        url = f"{base}/v1/messages"
        ensure_endpoint_allowed(url, config)

        payload: dict[str, object] = {
            "model": model,
            "max_tokens": config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self._token,
            "anthropic-version": ANTHROPIC_VERSION,
        }

        body = post_and_read(url, payload, headers, config)
        return _parse_message(body, config.provider, model)


def _parse_message(body: str, provider: str, model: str) -> AIResponse:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as error:
        raise AIProviderError("provider returned a non-JSON response") from error
    if not isinstance(data, dict):
        raise AIProviderError("provider response was not a JSON object")

    if data.get("stop_reason") == "refusal":
        raise AIProviderError("provider refused the request")

    content = data.get("content")
    if not isinstance(content, list):
        raise AIProviderError("provider response contained no content")
    text = "".join(
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ).strip()
    if not text:
        raise AIProviderError("provider response contained no message content")

    resolved_model = data.get("model")
    return AIResponse(
        provider=provider,
        model=resolved_model if isinstance(resolved_model, str) else model,
        text=text,
    )
