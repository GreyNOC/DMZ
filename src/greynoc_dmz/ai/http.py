from __future__ import annotations

from ..integrations.safety import SafetyPolicy, check_endpoint
from ..integrations.transport import TransportError, post_json
from .config import AIConfig
from .models import AIProviderError


def ensure_endpoint_allowed(url: str, config: AIConfig) -> None:
    """Block the request if the endpoint is not permitted by the safety policy.

    Local and private endpoints are always allowed. External endpoints (the
    public AI vendors) require ``allow_external`` so a lab stays isolated by
    default. The check never contacts the provider.
    """
    verdict = check_endpoint(
        url, SafetyPolicy(allow_external=config.allow_external, allowlist=frozenset())
    )
    if not verdict.allowed:
        raise AIProviderError(f"AI endpoint blocked: {verdict.reason}")


def post_and_read(
    url: str, payload: dict[str, object], headers: dict[str, str], config: AIConfig
) -> str:
    """POST ``payload`` and return the response body.

    Raises :class:`AIProviderError` on transport failure or a non-2xx status.
    The error message carries only an HTTP status and a short body snippet, never
    the request headers, so an API key can never leak into logs.
    """
    try:
        response = post_json(
            url,
            payload,
            headers=headers,
            timeout=config.timeout_seconds,
            verify_tls=True,
        )
    except TransportError as error:
        raise AIProviderError(str(error)) from error

    if not response.ok:
        snippet = response.body.strip().replace("\n", " ")[:200]
        raise AIProviderError(f"provider returned HTTP {response.status}: {snippet}")
    return response.body
