# GreyNOC DMZ

GreyNOC DMZ is an isolated lab for validating detection rules and SOC workflows with synthetic telemetry.

The app replays known events, runs detection rules, compares expected alerts with actual alerts, and writes evidence, history, and reports. It is built for local testing, operator training, integration readiness, and purple-team regression work.

## Status

Production-oriented scaffold. The core CLI, rule engine, reports, dashboard, local authentication, API status endpoint, working outbound integration adapters (file, webhook, Splunk HEC, Jira), a vendor-neutral AI provider layer, training-data export, tests, Docker build, CI workflow, scheduled bot workflow, and production readiness checklist are included. Inbound telemetry adapters and provider-specific EDR adapters are planned.

## What this repo is for

- Testing detection rules against synthetic telemetry
- Running repeatable red, blue, and purple team scenarios
- Training SOC workflows without customer data
- Checking that alerts include enough context for triage
- Producing evidence bundles, history records, and validation reports
- Reviewing validation status in a clean system-manager style dashboard
- Preparing controlled integrations with SIEM, EDR, ticketing, and cloud systems

## What this repo is not for

- Testing against public targets
- Storing credentials, customer logs, or sensitive data
- Running malware, persistence, evasion, or destructive actions
- Replacing a production SIEM, EDR, or case-management system

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'

greynoc-dmz security-check
greynoc-dmz lint
greynoc-dmz test-rules
greynoc-dmz integration-check
greynoc-dmz validate-all
greynoc-dmz integration-publish
greynoc-dmz ai-check
greynoc-dmz export-dataset

greynoc-dmz dashboard --host 127.0.0.1 --port 8787
```

Open the dashboard at `http://127.0.0.1:8787`.

Run one scenario:

```bash
greynoc-dmz run-scenario --scenario scenarios/auth-bruteforce-sim.json
```

Run two AI profiles against each other in a local synthetic dominance exercise:

```bash
greynoc-dmz ai-battle --ai-one Sentinel --ai-two Phantom --rounds 5 --ai-one-strategy balanced --ai-two-strategy adaptive
```

Run with Docker:

```bash
docker compose up --build
```

## Windows release install

GitHub Releases include a portable Windows executable and installer launchers.

Download and run the installer from the latest release:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-greynoc-dmz.ps1 -AddToPath
```

Or run the portable executable directly:

```powershell
.\greynoc-dmz.exe --help
.\greynoc-dmz.exe validate-all
```

Double-clicking `greynoc-dmz.exe` opens the local dashboard and keeps a console
window open with the dashboard URL. Close that window to stop the dashboard.
On first portable launch, bundled lab files are copied into
`%LOCALAPPDATA%\GreyNOC\DMZ\lab` so dashboard validation history, reports, and
evidence persist across runs.

## Local authentication

Authentication is off by default for local development. It can be enabled with the documented GreyNOC DMZ environment variables before starting the dashboard.

When authentication is enabled:

- `/`, `/scenario`, and `/api/status` require a session cookie
- `/login` accepts local username and secret-based login
- `/logout` clears the session cookie
- session cookies use `HttpOnly` and `SameSite=Strict`

Do not expose this dashboard directly to the internet. Put a real reverse proxy, TLS, and identity provider in front of it before any shared or remote use.

## Layout

```text
.github/workflows/           CI and scheduled DMZ bot workflow
apps/dashboard/              Dashboard notes and static assets
detections/rules/            Detection rules
detections/tests/            Per-rule true-positive / true-negative test cases
docs/                        Design notes, operating guides, readiness checklist
evidence/                    Generated evidence, ignored by git
infra/local-lab/             Local lab notes
reports/                     Generated reports, ignored by git
runbooks/                    Triage notes for starter detections
scenarios/                   Repeatable validation scenarios
src/greynoc_dmz/             CLI, rule engine, dashboard, auth, integrations, reports, security checks
telemetry/fixtures/          Synthetic telemetry
tests/                       Unit and regression tests
```

Generated local history is written under `.dmz/` and ignored by git.

## Validation flow

1. Select a scenario.
2. Replay the fixture telemetry.
3. Run the detection rules.
4. Compare expected alerts with actual alerts.
5. Save evidence.
6. Save a local history record.
7. Generate a report.
8. Tune and retest.

## AI battle arena

The AI battle arena puts two named AI profiles into a deterministic local contest. Each profile gets generated tactical stats, chooses from safe SOC-style strategies, and competes across synthetic challenges such as telemetry triage, containment, evidence handling, rule adaptation, false-positive reduction, and recovery prioritization.

Available strategies:

- `balanced`
- `aggressive`
- `defensive`
- `adaptive`
- `analyst`

CLI example:

```bash
greynoc-dmz ai-battle --ai-one Sentinel --ai-two Phantom --rounds 7 --objective "Own the SOC workflow without losing evidence"
```

Dashboard route:

```text
http://127.0.0.1:8787/ai-battle
```

JSON API example:

```text
http://127.0.0.1:8787/api/ai-battle?one=Sentinel&two=Phantom&rounds=5&one_strategy=balanced&two_strategy=adaptive
```

This feature is intentionally synthetic. It does not launch tools, attack systems, or run autonomous offensive activity.

## MITRE ATT&CK coverage

`greynoc-dmz coverage` maps every detection rule onto the enterprise ATT&CK tactic
list and reports which tactics are covered and which are gaps. Technique IDs are
listed separately, and any rule without a MITRE mapping is flagged.

```bash
greynoc-dmz coverage
```

The same data is available in the dashboard at `/coverage` and as JSON at
`/api/coverage`. The main dashboard and `/api/status` show the tactic coverage
ratio at a glance.

## Rule linting

`greynoc-dmz lint` validates detections and scenarios as code before they ship:

- every rule loads and validates against the schema
- rule ids are unique
- linked runbooks exist on disk
- MITRE ids are well formed (`TA####` or `T####[.###]`)
- thresholds and windows are sane
- scenarios only reference rules that exist, with telemetry that exists

It exits non-zero on any `error`-level finding, so it runs in CI as a gate.
`warning`-level findings (such as a rule with no MITRE mapping) do not fail the
build.

```bash
greynoc-dmz lint
```

## Detection-as-code testing

Every rule ships with a test case under `detections/tests/<RULE-ID>.json` holding
`true_positive` and `true_negative` events. `greynoc-dmz test-rules` replays each
case against its rule and fails when a true-positive does not fire or a
true-negative does. This is how a rule proves it both catches what it should and
stays quiet on what it should not.

```bash
greynoc-dmz test-rules
```

```json
{
  "rule_id": "GNOC-EXEC-001",
  "true_positive": [ { "event_type": "process_event", "message": "powershell -enc SQBFAFgA", "...": "..." } ],
  "true_negative": [ { "event_type": "process_event", "message": "powershell Get-ChildItem", "...": "..." } ]
}
```

`lint` warns when a rule has no test file, and `test-rules` runs as a CI gate.

## Incidents and detection latency

Alerts carry a `dwell_seconds` value (the span from first to last event) as a
detection-latency proxy. Reports and the scenario detail page correlate alerts
by host into incidents, each showing the combined max severity, the rules that
fired, the ATT&CK tactics and techniques involved, total alerts and events, and
the incident dwell time. This turns a flat alert list into a per-host kill-chain
view.

## Integrations

GreyNOC DMZ publishes detection-validation results into existing security
tooling through small vendor-neutral adapters. Built-in adapters:

- `file` — local NDJSON feed (no network; safe default)
- `webhook` — any JSON HTTP endpoint (MSP dashboards, SOAR, EDR/XDR intake)
- `splunk_hec` — Splunk HTTP Event Collector
- `jira` — opens a ticket when a scenario fails

Integrations are defined in `configs/integrations.json`, which references
credentials only by environment-variable name and is safe to commit.

```bash
greynoc-dmz integration-check            # show configured integrations
greynoc-dmz integration-publish          # dry run: preview what would be sent
greynoc-dmz integration-publish --send   # transmit to ready integrations
```

Integrations are disabled by default. External endpoints are blocked unless
`GREYNOC_DMZ_ALLOW_EXTERNAL=1` is set or the host is allowlisted. See
`docs/integrations.md` for adapter details, configuration, and the safety model.

## AI providers

Teams can plug in their own AI provider (hosted or local) for advisory analysis
of detection-validation results. AI is disabled by default and is configured
entirely through `GREYNOC_DMZ_AI_*` environment variables.

```bash
greynoc-dmz ai-check          # report AI readiness (no provider call)
greynoc-dmz ai-check --live   # confirm connectivity with one live call
greynoc-dmz ai-review         # AI advisory review of validation results
```

The `openai_compatible` adapter covers the OpenAI API, Azure OpenAI, and local
servers (Ollama, LM Studio, vLLM). API keys are read from a named environment
variable at call time, never stored in config or git. External provider
endpoints are blocked unless `GREYNOC_DMZ_AI_ALLOW_EXTERNAL=true`, and AI output
is advisory only. See `docs/ai-providers.md` for configuration and safety.

## Training data

Every scenario run can be exported as a labeled record for training or
fine-tuning a security AI model — DMZ as a training-data factory. Each scenario
added to the lab becomes another labeled example.

```bash
greynoc-dmz export-dataset                 # raw labeled JSONL
greynoc-dmz export-dataset --format chat   # OpenAI fine-tuning JSONL
greynoc-dmz export-dataset --with-ai       # add a per-scenario AI analysis note
```

Records carry the synthetic telemetry, the expected detections (the ground-truth
label), the alerts produced, the pass/fail outcome, and an optional AI note.
Generated datasets are written under `datasets/` and are not committed. See
`docs/training-data.md`.

## Dashboard

The dashboard uses a clean old-Windows/system-manager style. It shows scenario totals, alert count, MITRE ATT&CK tactic coverage, recent validation history, scenario detail pages, a coverage map, and the AI battle arena.

The dashboard is local-first and read-only: `GET` requests recompute results in memory but never write evidence or history. It serves static HTML and small JSON endpoints, and sets basic browser security headers.

## Role model

The role model defines `viewer`, `analyst`, `engineer`, and `admin` in
`src/greynoc_dmz/access.py`. When authentication is enabled, the dashboard
enforces the permission map per route:

- `viewer` and `analyst` see scenario status and detail (`/`, `/scenario`, `/api/status`)
- `engineer` and `admin` additionally reach the detection tooling (`/coverage`, `/ai-battle` and their APIs)

Routes a role lacks permission for return `403`. When authentication is
disabled for local development, requests run with the `admin` role.

## Rule format

Rules are JSON files under `detections/rules/`.

```json
{
  "id": "GNOC-AUTH-001",
  "name": "Repeated failed login attempts",
  "severity": "medium",
  "data_source": "auth",
  "event_type": "auth_failed",
  "match": { "message": "failed login" },
  "threshold": 5,
  "window_minutes": 10,
  "mitre": ["TA0006", "T1110"],
  "runbook": "runbooks/auth-bruteforce.md"
}
```

Threshold rules are window-aware. A rule with `threshold: 5` and `window_minutes: 10` only fires when five matching events occur inside the configured window.

### Match expressions

Each entry in `match` is checked against an event attribute (`message`, `source`,
`host`, `user`, `ip`, `event_type`) or, otherwise, against a key in the event's
`fields`. A match value can be:

- a string — case-insensitive substring (`contains`)
- a list — membership (`in`)
- an object `{ "op": ..., "value": ..., "negate": false }` for structured matching

Supported operators: `equals`/`eq`, `contains`, `startswith`, `endswith`,
`regex`, `in`, and the numeric comparisons `gt`, `gte`, `lt`, `lte` (which coerce
strings to numbers). Set `"negate": true` to invert any operator.

```json
"match": {
  "path": { "op": "regex", "value": "union\\s+select" },
  "status": { "op": "gte", "value": 400 },
  "user": { "op": "equals", "value": "service-account", "negate": true }
}
```

`greynoc-dmz lint` validates operator names and compiles every regex, so a broken
match expression fails CI instead of silently never firing.

## Security checks

Run this before each commit:

```bash
greynoc-dmz security-check
```

The scanner checks for common secret and risky shell-download markers in repository text files. It is not a full secret scanner, but it catches basic mistakes early.

CI runs:

```bash
ruff check .
mypy src
pytest
greynoc-dmz security-check
greynoc-dmz lint
greynoc-dmz test-rules
greynoc-dmz integration-check
greynoc-dmz validate-all
```

## DMZ bot

`.github/workflows/dmz-bot.yml` runs the same release gate on a weekly schedule and by manual dispatch.

## Production readiness

Use `docs/production-readiness.md` before any shared deployment. Use authentication, run behind TLS, restrict network access, keep generated data out of git, and do not expose the built-in dashboard directly to the public internet.

## Safety rules

Keep the lab isolated. Use owned systems or synthetic data only. Do not add real secrets, client data, production logs, or tooling that can be used outside the lab.

## Repository

https://github.com/GreyNOC/DMZ
