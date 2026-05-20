# GreyNOC DMZ

GreyNOC DMZ is an isolated lab for validating detection rules and SOC workflows with synthetic telemetry.

The app replays known events, runs detection rules, compares expected alerts with actual alerts, and writes evidence, history, and reports. It is built for local testing, operator training, and purple-team regression work.

## Status

Production-oriented scaffold. The core CLI, rule engine, reports, dashboard, local authentication, API status endpoint, tests, Docker build, CI workflow, scheduled bot workflow, and production readiness checklist are included. Integrations with real SIEM, EDR, ticketing, or cloud systems are future work.

## What this repo is for

- Testing detection rules against synthetic telemetry
- Running repeatable red, blue, and purple team scenarios
- Training SOC workflows without customer data
- Checking that alerts include enough context for triage
- Producing evidence bundles, history records, and validation reports
- Reviewing validation status in a clean system-manager style dashboard

## What this repo is not for

- Testing against public targets
- Storing credentials, customer logs, or sensitive data
- Running malware, persistence, evasion, or destructive actions
- Replacing a production SIEM, EDR, or case-management system

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'

greynoc-dmz security-check
greynoc-dmz validate-all

greynoc-dmz dashboard --host 127.0.0.1 --port 8787
```

Open the dashboard:

```text
http://127.0.0.1:8787
```

Check API status:

```text
http://127.0.0.1:8787/api/status
```

Run one scenario:

```bash
greynoc-dmz run-scenario --scenario scenarios/auth-bruteforce-sim.json
```

Run with Docker:

```bash
docker compose up --build
```

## Optional local authentication

Authentication is off by default for local development. Turn it on by setting a password before starting the dashboard:

```bash
export GREYNOC_DMZ_USERNAME=admin
export GREYNOC_DMZ_PASSWORD='change-this-local-password'
export GREYNOC_DMZ_ROLE=admin

greynoc-dmz dashboard --host 127.0.0.1 --port 8787
```

When authentication is enabled:

- `/`, `/scenario`, and `/api/status` require a session cookie
- `/login` accepts local username/password login
- `/logout` clears the session cookie
- session cookies use `HttpOnly` and `SameSite=Strict`

Do not expose this dashboard directly to the internet. Put a real reverse proxy, TLS, and identity provider in front of it before any shared or remote use.

## Layout

```text
.github/workflows/           CI and scheduled DMZ bot workflow
apps/dashboard/              Dashboard notes and static assets
detections/rules/            Detection rules
docs/                        Design notes, operating guides, readiness checklist
evidence/                    Generated evidence, ignored by git
infra/local-lab/             Local lab notes
reports/                     Generated reports, ignored by git
runbooks/                    Triage notes for starter detections
scenarios/                   Repeatable validation scenarios
src/greynoc_dmz/             CLI, rule engine, dashboard, auth, reports, security checks
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

## Dashboard

The dashboard uses a clean old-Windows/system-manager style. It shows:

- scenario count
- passing and failing totals
- alert count
- fired, missing, and unexpected rules
- recent validation history
- scenario detail pages

The dashboard is local-first. It serves static HTML and a small JSON status endpoint. It also sets basic browser security headers.

## Role model

The role model defines these roles:

- `viewer`
- `analyst`
- `engineer`
- `admin`

The first authentication pass stores the selected role in the session. Fine-grained route enforcement is still limited because most routes are read-only. Future write routes should check the permission map in `src/greynoc_dmz/access.py`.

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
greynoc-dmz validate-all
```

## DMZ bot

`.github/workflows/dmz-bot.yml` runs the same release gate on a weekly schedule and by manual dispatch. It is the first automation bot for repo health checks.

## Production readiness

Use `docs/production-readiness.md` before any shared deployment. The short version is:

- use authentication
- run behind TLS
- restrict network access
- keep generated data out of git
- run the release gate before every merge
- do not expose the built-in dashboard directly to the public internet

## Safety rules

Keep the lab isolated. Use owned systems or synthetic data only. Do not add real secrets, client data, production logs, or tooling that can be used outside the lab.

## Repository

https://github.com/GreyNOC/DMZ
