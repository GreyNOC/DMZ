# AI Provider Implementation Plan

> Status: implemented. The provider layer, OpenAI-compatible adapter, `ai-check`, and `ai-review` are built — see `docs/ai-providers.md`. Remaining roadmap: provider-specific adapters and training-data export.

GreyNOC DMZ should support user-selected AI APIs through a vendor-neutral provider layer. The goal is to let users bring their preferred hosted or local AI provider without tying the project to one vendor.

This plan follows the existing integration direction in `docs/integrations.md` and `src/greynoc_dmz/integrations.py`: keep provider-specific code behind small interfaces, keep credentials out of git, and default to safe local lab behavior.

## Goals

- Let users configure their preferred AI provider.
- Support OpenAI-compatible APIs first because many hosted and local model servers use that shape.
- Support provider-specific adapters later only when required.
- Keep all API keys in environment variables or an external secret manager.
- Avoid sending customer logs or sensitive data to external AI services by default.
- Make AI output clearly advisory and AI-assisted.
- Keep the core validation engine independent from any AI vendor SDK.

## Non-goals

- Do not make AI required for running DMZ.
- Do not commit API keys, prompts containing sensitive data, or provider secrets.
- Do not allow AI responses to execute commands or change detections automatically.
- Do not send real customer telemetry to external services by default.
- Do not replace analyst review, rule validation, or evidence generation.

## Proposed architecture

Add a small AI package:

```text
src/greynoc_dmz/ai/
  __init__.py
  config.py
  providers.py
  openai_compatible.py
  router.py
```

### Provider protocol

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AIResponse:
    provider: str
    model: str
    text: str


class AIProvider(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        """Return an advisory AI response for a DMZ workflow."""
```

### Configuration model

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    provider: str = "disabled"
    model: str | None = None
    base_url: str | None = None
    token_env: str | None = None
    timeout_seconds: int = 30
    temperature: float = 0.2
    allow_external: bool = False
```

Environment variables:

```bash
GREYNOC_DMZ_AI_ENABLED=false
GREYNOC_DMZ_AI_PROVIDER=openai_compatible
GREYNOC_DMZ_AI_BASE_URL=https://api.openai.com/v1
GREYNOC_DMZ_AI_MODEL=gpt-4.1-mini
GREYNOC_DMZ_AI_TOKEN_ENV=OPENAI_API_KEY
GREYNOC_DMZ_AI_ALLOW_EXTERNAL=false
OPENAI_API_KEY=replace-me-outside-git
```

Local model example:

```bash
GREYNOC_DMZ_AI_ENABLED=true
GREYNOC_DMZ_AI_PROVIDER=openai_compatible
GREYNOC_DMZ_AI_BASE_URL=http://127.0.0.1:11434/v1
GREYNOC_DMZ_AI_MODEL=llama3.1
GREYNOC_DMZ_AI_TOKEN_ENV=
GREYNOC_DMZ_AI_ALLOW_EXTERNAL=false
```

## Provider support order

### Phase 1: OpenAI-compatible adapter

Build one adapter that works with providers exposing a `/chat/completions`-style API.

Initial compatible targets may include:

- OpenAI API
- Azure OpenAI if configured with the proper base URL
- Local servers that expose OpenAI-compatible endpoints
- Other hosted providers with compatible request/response shapes

Implementation preference:

- Use Python standard library HTTP first if practical.
- Avoid introducing a hard dependency on one vendor SDK.
- Add optional dependencies only when they provide clear value.

### Phase 2: Provider-specific adapters

Add specific adapters only when the provider differs enough to justify it:

- Anthropic-compatible adapter
- Google Gemini-compatible adapter
- Local-only adapter wrappers if needed

### Phase 3: UI and workflow integration

Once the provider layer is stable:

- Show provider readiness in dashboard status.
- Add AI-assisted scenario summaries.
- Add AI-assisted detection tuning suggestions.
- Add AI-assisted analyst notes in generated reports.

## CLI commands

Add:

```bash
greynoc-dmz ai-check
```

The command should report:

- enabled or disabled
- provider name
- selected model
- base URL presence
- token environment variable presence when required
- whether external AI use is allowed
- optional live test status when `--live` is passed

Example:

```bash
greynoc-dmz ai-check
```

Example with live provider test:

```bash
greynoc-dmz ai-check --live
```

The default check should not call external APIs. `--live` should be explicit.

## Safety controls

### Credential handling

- Store only the name of the token environment variable in config.
- Read the actual token from the environment at runtime.
- Never print token values.
- Extend `security-check` patterns if needed to catch common AI key names.

### Data handling

- Default `GREYNOC_DMZ_AI_ALLOW_EXTERNAL=false`.
- If the configured base URL is not localhost/private and external use is not allowed, block the request.
- Keep AI disabled by default.
- Only send synthetic scenario summaries unless the user explicitly opts in.

### Prompt handling

- Keep prompts short and purpose-specific.
- Include a system message reminding the model that outputs are advisory.
- Do not ask the model to produce executable shell commands for automatic execution.
- Mark AI-generated text as AI-assisted in reports.

## Integration with existing code

### `src/greynoc_dmz/integrations.py`

Add AI to `IntegrationKind`:

```python
class IntegrationKind(StrEnum):
    siem = "siem"
    edr = "edr"
    ticketing = "ticketing"
    cloud = "cloud"
    ai = "ai"
```

Add a default disabled AI integration:

```python
IntegrationConfig(name="generic-ai", kind=IntegrationKind.ai)
```

### `src/greynoc_dmz/cli.py`

Add an `ai-check` command next to `integration-check`.

The command should use the new AI config loader and readiness checker.

### Dashboard API

Add AI readiness to `/api/status` only after the CLI layer is tested.

The dashboard should display:

- AI disabled
- AI configured but not live-tested
- AI ready
- AI blocked by safety policy

## Testing plan

Add unit tests for:

- default AI config is disabled
- env config loads expected fields
- missing model reports missing config
- missing token env reports missing config when required
- local provider URL does not require external allowance
- public provider URL is blocked unless external use is explicitly allowed
- OpenAI-compatible response parsing handles expected response JSON
- OpenAI-compatible adapter handles provider errors without leaking secrets

No tests should require live external API calls.

## Documentation updates

Update:

- `README.md`
- `docs/integrations.md`
- `docs/production-readiness.md`

Add examples for:

- hosted provider
- local provider
- disabled mode
- live check
- external AI safety warning

## Suggested milestones

### Milestone 1: Planning and config

- Add this plan.
- Add AI config model.
- Add AI readiness check model.
- Add tests for config and safety policy.

### Milestone 2: OpenAI-compatible adapter

- Add provider protocol.
- Add OpenAI-compatible adapter.
- Add mocked response tests.
- Add `ai-check` command.

### Milestone 3: Report integration

- Add optional AI-assisted scenario summary generation.
- Add report appendix section for AI output.
- Make the feature disabled by default.

### Milestone 4: Dashboard integration

- Add status endpoint fields.
- Add dashboard AI readiness panel.
- Keep provider invocation behind explicit user action.

## Acceptance criteria

- DMZ runs normally with AI disabled.
- `greynoc-dmz ai-check` works without external network calls by default.
- Users can configure a provider without code changes.
- API keys are never printed or stored in git.
- Public AI calls are blocked unless explicitly allowed.
- Unit tests cover config loading, safety gating, and provider response parsing.
- Reports clearly label AI-assisted content.

## Open questions

- Should AI provider settings live only in environment variables, or should DMZ support a local ignored config file such as `.dmz/ai.toml`?
- Should AI-assisted summaries be written into evidence history by default, or only into reports?
- Should external AI use require both an environment flag and a CLI flag for live calls?
- Should the dashboard support AI actions in Phase 3, or should AI remain CLI/report-only until authentication is hardened?
