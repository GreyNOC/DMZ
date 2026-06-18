# AI providers

GreyNOC DMZ lets a team bring their own AI provider — hosted or local — through
a vendor-neutral adapter. AI output is advisory only; the core validation engine
never depends on it, and AI is disabled by default.

## How it works

1. The AI layer is configured through `GREYNOC_DMZ_AI_*` environment variables.
2. `ai-check` reports readiness without contacting the provider.
3. `ai-review` asks the provider to analyse detection-validation results.
4. An endpoint safety gate runs before any external call.

## Supported providers

The `openai_compatible` adapter works with any service that exposes an
OpenAI-style `/chat/completions` API:

- OpenAI API
- Azure OpenAI (configured with a matching base URL)
- Local model servers — Ollama, LM Studio, vLLM
- Other hosted providers with a compatible request/response shape

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `GREYNOC_DMZ_AI_ENABLED` | Turn the AI layer on | `false` |
| `GREYNOC_DMZ_AI_PROVIDER` | Adapter name (`openai_compatible`) | `disabled` |
| `GREYNOC_DMZ_AI_BASE_URL` | Provider API base URL | unset |
| `GREYNOC_DMZ_AI_MODEL` | Model name | unset |
| `GREYNOC_DMZ_AI_TOKEN_ENV` | Name of the env var holding the API key | unset |
| `GREYNOC_DMZ_AI_ALLOW_EXTERNAL` | Permit non-local provider endpoints | `false` |
| `GREYNOC_DMZ_AI_TIMEOUT_SECONDS` | Request timeout | `30` |
| `GREYNOC_DMZ_AI_TEMPERATURE` | Sampling temperature | `0.2` |

The API key is never named in DMZ config or git. `GREYNOC_DMZ_AI_TOKEN_ENV`
holds the *name* of a separate environment variable, and DMZ reads the key from
that variable at call time.

### Hosted provider

```bash
export GREYNOC_DMZ_AI_ENABLED=true
export GREYNOC_DMZ_AI_PROVIDER=openai_compatible
export GREYNOC_DMZ_AI_BASE_URL=https://api.openai.com/v1
export GREYNOC_DMZ_AI_MODEL=gpt-4.1-mini
export GREYNOC_DMZ_AI_TOKEN_ENV=OPENAI_API_KEY
export GREYNOC_DMZ_AI_ALLOW_EXTERNAL=true
export OPENAI_API_KEY=replace-me-outside-git
```

### Local provider

```bash
export GREYNOC_DMZ_AI_ENABLED=true
export GREYNOC_DMZ_AI_PROVIDER=openai_compatible
export GREYNOC_DMZ_AI_BASE_URL=http://127.0.0.1:11434/v1
export GREYNOC_DMZ_AI_MODEL=llama3.1
```

A local endpoint needs no API key and no external allowance.

## Safety model

- AI is disabled unless `GREYNOC_DMZ_AI_ENABLED` is truthy.
- Local and private endpoints are always allowed.
- External endpoints are blocked unless `GREYNOC_DMZ_AI_ALLOW_EXTERNAL=true`.
- The API key is read from the environment at call time and is never logged.
- Only synthetic scenario summaries are sent; DMZ scenario data is synthetic by
  design.
- AI output is advisory. DMZ never lets AI output run commands or change a
  detection rule.

## Commands

```bash
greynoc-dmz ai-check          # report AI readiness (no provider call)
greynoc-dmz ai-check --live   # confirm connectivity with one live call
greynoc-dmz ai-review         # AI advisory review of validation results
```

## Planned

- Anthropic and Google Gemini provider adapters
- AI-assisted report appendices
- Export of AI-reviewed scenario runs as model-training datasets
