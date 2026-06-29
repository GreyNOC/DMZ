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

Three vendor-neutral adapters cover the major AI APIs. Every adapter goes through
the same endpoint safety gate and credential-safe transport, so an API key can
never leak into a log or error message regardless of provider.

| Provider value | API | Notes |
|---|---|---|
| `openai_compatible` (alias `openai`) | OpenAI-style `/chat/completions` | OpenAI, Azure OpenAI, and local servers (Ollama, LM Studio, vLLM) |
| `anthropic` (alias `claude`) | Anthropic Messages API (`/v1/messages`) | `x-api-key` auth; `base_url` defaults to `https://api.anthropic.com`. Sampling temperature is omitted so every current Claude model is supported |
| `gemini` (alias `google`) | Google Gemini `generateContent` | Key sent in the `x-goog-api-key` header (never the URL); `base_url` defaults to the Generative Language API |

`base_url` is optional for `anthropic` and `gemini` (a sensible default is used)
and required for `openai_compatible`.

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
| `GREYNOC_DMZ_AI_MAX_TOKENS` | Max response tokens (used by Anthropic) | `1024` |

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

### Anthropic (Claude)

```bash
export GREYNOC_DMZ_AI_ENABLED=true
export GREYNOC_DMZ_AI_PROVIDER=anthropic
export GREYNOC_DMZ_AI_MODEL=claude-opus-4-8
export GREYNOC_DMZ_AI_TOKEN_ENV=ANTHROPIC_API_KEY
export GREYNOC_DMZ_AI_ALLOW_EXTERNAL=true
export ANTHROPIC_API_KEY=replace-me-outside-git
```

### Google Gemini

```bash
export GREYNOC_DMZ_AI_ENABLED=true
export GREYNOC_DMZ_AI_PROVIDER=gemini
export GREYNOC_DMZ_AI_MODEL=gemini-2.0-flash
export GREYNOC_DMZ_AI_TOKEN_ENV=GEMINI_API_KEY
export GREYNOC_DMZ_AI_ALLOW_EXTERNAL=true
export GEMINI_API_KEY=replace-me-outside-git
```

## Battle arena: roster and live battles

Beyond single-provider advisory review, DMZ can field many named AI fighters at
once and pit them against each other on synthetic SOC challenges, with a live AI
model acting as the judge.

A **roster** lists fighters in `configs/ai-roster.json`. Each fighter is a
provider config with a name; like everything else, API keys are referenced only
by environment-variable name, so the roster is safe to commit:

```json
{
  "fighters": [
    {"name": "Claude", "provider": "anthropic", "model": "claude-opus-4-8", "token_env": "ANTHROPIC_API_KEY"},
    {"name": "GPT", "provider": "openai_compatible", "model": "gpt-4.1-mini", "base_url": "https://api.openai.com/v1", "token_env": "OPENAI_API_KEY"},
    {"name": "Gemini", "provider": "gemini", "model": "gemini-2.0-flash", "token_env": "GEMINI_API_KEY"},
    {"name": "Local", "provider": "openai_compatible", "model": "llama3.1", "base_url": "http://localhost:11434/v1"}
  ]
}
```

```bash
greynoc-dmz ai-roster                       # list fighters and per-fighter readiness
greynoc-dmz ai-roster --allow-external      # readiness as if external endpoints were permitted

# Head-to-head: real models answer each challenge, an AI judge scores them
greynoc-dmz live-battle --fighters Claude,GPT --judge Gemini --rounds 5 --allow-external

# Collaborative teams: teammates build on each other, then teams are judged
greynoc-dmz collab-battle --teams "Red=Claude,GPT;Blue=Gemini,Local" --judge Claude --allow-external
```

Both battle commands accept `--objective`, `--roster <path>`, and `--json`. The
judge defaults to a roster fighter that is not a combatant. Live and collaborative
battles make outbound provider calls and require `--allow-external` for hosted
providers (local endpoints need no allowance).

### From the dashboard

The dashboard can also run battles, at `/live-battle` (engineer/admin role).
It offers a head-to-head form and a collaborative-team form; each posts to a
`/run-battle` or `/run-collab` action that starts the battle in a background
worker and redirects to a progress page at `/battle?id=...`. That page updates
itself with a no-JavaScript meta refresh — rounds appear as they complete and a
long battle never blocks the browser — then settles on the scoreboard, round
log, and judge rationale (and stops refreshing) when the battle finishes. A
JSON view of the same job is at `/api/battle?id=...`.

Hosted providers require ticking **Allow external endpoints** per run, mirroring
the CLI's `--allow-external`; a battle is refused before it starts if a fighter
or judge is not ready. The roster status view at `/roster` (and `/api/roster`)
stays read-only and never contacts a provider. Because battles spend tokens and
reach external services, keep authentication on and do not expose the dashboard
to the internet.

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
greynoc-dmz ai-roster         # list battle-arena fighters and readiness
greynoc-dmz live-battle       # real head-to-head AI battle, judged live
greynoc-dmz collab-battle     # collaborative team AI battle, judged live
```

## Planned

- AI-assisted report appendices
- Export of AI-reviewed scenario runs as model-training datasets
