from __future__ import annotations

import json

from .config import AIConfig
from .http import ensure_endpoint_allowed, post_and_read
from .models import AIProviderError, AIResponse

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GoogleGeminiProvider:
    """AI provider for Google's Gemini ``generateContent`` API.

    The API key travels in the ``x-goog-api-key`` header rather than the URL
    query string, so it never lands in request logs or error snippets.
    """

    name = "gemini"

    def __init__(self, config: AIConfig, token: str | None) -> None:
        self._config = config
        self._token = token

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        config = self._config
        base = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
        if not config.model:
            raise AIProviderError("AI model is not configured")
        if not self._token:
            raise AIProviderError("Gemini provider requires an API key")
        model = config.model

        url = f"{base}/models/{model}:generateContent"
        ensure_endpoint_allowed(url, config)

        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": config.temperature},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        headers = {"x-goog-api-key": self._token}

        body = post_and_read(url, payload, headers, config)
        return _parse_generation(body, config.provider, model)


def _parse_generation(body: str, provider: str, model: str) -> AIResponse:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as error:
        raise AIProviderError("provider returned a non-JSON response") from error
    if not isinstance(data, dict):
        raise AIProviderError("provider response was not a JSON object")

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        feedback = data.get("promptFeedback")
        if isinstance(feedback, dict) and feedback.get("blockReason"):
            raise AIProviderError(f"provider blocked the prompt: {feedback['blockReason']}")
        raise AIProviderError("provider response contained no candidates")

    first = candidates[0]
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        # A candidate-level block (e.g. SAFETY, RECITATION) returns a candidate
        # with a blocking finishReason and no parts. Surface that reason rather
        # than a vague parse error.
        finish_reason = first.get("finishReason") if isinstance(first, dict) else None
        if isinstance(finish_reason, str) and finish_reason not in {"STOP", "MAX_TOKENS", ""}:
            raise AIProviderError(f"provider blocked the response: {finish_reason}")
        raise AIProviderError("provider response contained no content parts")
    text = "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()
    if not text:
        raise AIProviderError("provider response contained no message content")

    resolved_model = data.get("modelVersion")
    return AIResponse(
        provider=provider,
        model=resolved_model if isinstance(resolved_model, str) else model,
        text=text,
    )
