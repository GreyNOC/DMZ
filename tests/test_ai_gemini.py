import json

import pytest
from conftest import RecordingServer

from greynoc_dmz.ai import AIConfig, GoogleGeminiProvider
from greynoc_dmz.ai.models import AIProviderError

_GENERATION = json.dumps(
    {
        "candidates": [{"content": {"parts": [{"text": "Triage the true signal first."}]}}],
        "modelVersion": "gemini-resolved",
    }
)


def _config(server: RecordingServer) -> AIConfig:
    return AIConfig(
        enabled=True,
        provider="gemini",
        base_url=f"http://127.0.0.1:{server.server_address[1]}",
        model="gemini-test",
    )


def test_provider_completes_and_parses_text(recording_server: RecordingServer) -> None:
    recording_server.reply_body = _GENERATION
    provider = GoogleGeminiProvider(_config(recording_server), token="goog-key")

    response = provider.complete("hello", system="be brief")

    assert response.text == "Triage the true signal first."
    assert response.model == "gemini-resolved"
    captured = recording_server.captured[0]
    assert captured.path == "/models/gemini-test:generateContent"
    sent = json.loads(captured.body)
    assert sent["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert sent["contents"][0]["parts"][0]["text"] == "hello"


def test_provider_sends_key_in_header_not_url(recording_server: RecordingServer) -> None:
    recording_server.reply_body = _GENERATION
    GoogleGeminiProvider(_config(recording_server), token="goog-secret").complete("hi")

    captured = recording_server.captured[0]
    assert captured.headers["x-goog-api-key"] == "goog-secret"
    assert "goog-secret" not in captured.path


def test_provider_sends_temperature(recording_server: RecordingServer) -> None:
    recording_server.reply_body = _GENERATION
    GoogleGeminiProvider(_config(recording_server), token="goog-key").complete("hi")

    sent = json.loads(recording_server.captured[0].body)
    assert sent["generationConfig"]["temperature"] == pytest.approx(0.2)


def test_provider_surfaces_candidate_level_block(recording_server: RecordingServer) -> None:
    recording_server.reply_body = json.dumps({"candidates": [{"finishReason": "SAFETY"}]})
    provider = GoogleGeminiProvider(_config(recording_server), token="goog-key")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "SAFETY" in str(excinfo.value)


def test_provider_requires_api_key(recording_server: RecordingServer) -> None:
    provider = GoogleGeminiProvider(_config(recording_server), token=None)

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "api key" in str(excinfo.value).lower()


def test_provider_surfaces_blocked_prompt(recording_server: RecordingServer) -> None:
    recording_server.reply_body = json.dumps({"promptFeedback": {"blockReason": "SAFETY"}})
    provider = GoogleGeminiProvider(_config(recording_server), token="goog-key")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "blocked" in str(excinfo.value).lower()


def test_provider_http_error_does_not_leak_key(recording_server: RecordingServer) -> None:
    recording_server.reply_status = 403
    recording_server.reply_body = "permission denied"
    provider = GoogleGeminiProvider(_config(recording_server), token="goog-supersecret")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "403" in str(excinfo.value)
    assert "goog-supersecret" not in str(excinfo.value)
