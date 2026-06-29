from __future__ import annotations

import json

from .config import AIConfig
from .http import ensure_endpoint_allowed, post_and_read
from .models import AIProviderError, AIResponse


class OpenAICompatibleProvider:
    """AI provider for any service exposing an OpenAI-style chat completions API.

    Covers the OpenAI API, Azure OpenAI configured with a matching base URL, and
    local model servers (Ollama, LM Studio, vLLM) that expose a compatible
    ``/chat/completions`` endpoint.
    """

    name = "openai_compatible"

    def __init__(self, config: AIConfig, token: str | None) -> None:
        self._config = config
        self._token = token

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        config = self._config
        base = (config.base_url or "").rstrip("/")
        if not base:
            raise AIProviderError("AI base URL is not configured")
        if not config.model:
            raise AIProviderError("AI model is not configured")
        model = config.model

        url = f"{base}/chat/completions"
        ensure_endpoint_allowed(url, config)

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
        }
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        body = post_and_read(url, payload, headers, config)
        return _parse_completion(body, config.provider, model)


def _parse_completion(body: str, provider: str, model: str) -> AIResponse:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as error:
        raise AIProviderError("provider returned a non-JSON response") from error
    if not isinstance(data, dict):
        raise AIProviderError("provider response was not a JSON object")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIProviderError("provider response contained no choices")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise AIProviderError("provider response contained no message content")

    resolved_model = data.get("model")
    return AIResponse(
        provider=provider,
        model=resolved_model if isinstance(resolved_model, str) else model,
        text=content.strip(),
    )
