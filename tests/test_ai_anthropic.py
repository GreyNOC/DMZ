import json

import pytest
from conftest import RecordingServer

from greynoc_dmz.ai import AIConfig, AnthropicProvider
from greynoc_dmz.ai.models import AIProviderError

_MESSAGE = json.dumps(
    {
        "model": "claude-resolved",
        "stop_reason": "end_turn",
        "content": [
            {"type": "thinking", "thinking": "..."},
            {"type": "text", "text": "Contain first, preserve evidence."},
        ],
    }
)


def _config(server: RecordingServer, temperature: float = 0.2) -> AIConfig:
    return AIConfig(
        enabled=True,
        provider="anthropic",
        base_url=f"http://127.0.0.1:{server.server_address[1]}",
        model="claude-test",
        temperature=temperature,
    )


def test_provider_completes_and_parses_text(recording_server: RecordingServer) -> None:
    recording_server.reply_body = _MESSAGE
    provider = AnthropicProvider(_config(recording_server), token="sk-ant-test")

    response = provider.complete("hello", system="be brief")

    assert response.text == "Contain first, preserve evidence."
    assert response.model == "claude-resolved"
    captured = recording_server.captured[0]
    assert captured.path == "/v1/messages"
    assert captured.headers["x-api-key"] == "sk-ant-test"
    assert captured.headers["anthropic-version"] == "2023-06-01"
    sent = json.loads(captured.body)
    assert sent["system"] == "be brief"
    assert sent["messages"][0]["content"] == "hello"
    assert sent["max_tokens"] == 1024


def test_provider_omits_temperature(recording_server: RecordingServer) -> None:
    # The latest Claude models reject sampling params; the adapter must not send one.
    recording_server.reply_body = _MESSAGE
    AnthropicProvider(_config(recording_server, temperature=0.7), token="sk").complete("hi")

    sent = json.loads(recording_server.captured[0].body)
    assert "temperature" not in sent


def test_provider_requires_api_key(recording_server: RecordingServer) -> None:
    provider = AnthropicProvider(_config(recording_server), token=None)

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "api key" in str(excinfo.value).lower()


def test_provider_surfaces_refusal(recording_server: RecordingServer) -> None:
    recording_server.reply_body = json.dumps({"stop_reason": "refusal", "content": []})
    provider = AnthropicProvider(_config(recording_server), token="sk")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "refus" in str(excinfo.value).lower()


def test_provider_http_error_does_not_leak_key(recording_server: RecordingServer) -> None:
    recording_server.reply_status = 401
    recording_server.reply_body = "authentication failed"
    provider = AnthropicProvider(_config(recording_server), token="sk-ant-supersecret")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "401" in str(excinfo.value)
    assert "sk-ant-supersecret" not in str(excinfo.value)


def test_provider_blocks_external_endpoint_without_allowance() -> None:
    config = AIConfig(enabled=True, provider="anthropic", model="claude-opus-4-8")
    provider = AnthropicProvider(config, token="sk-ant-test")

    with pytest.raises(AIProviderError) as excinfo:
        provider.complete("hello")

    assert "blocked" in str(excinfo.value).lower()
