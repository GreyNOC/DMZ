# GreyNOC DMZ

GreyNOC DMZ is an isolated lab for testing detection logic, telemetry handling, alert review, and purple-team validation.

The goal is simple: replay known activity, verify the expected detections, collect evidence, and improve the rule or workflow when something misses.

## Status

Starter scaffold. Not production software yet.

## What this repo is for

- Testing detection rules against synthetic telemetry
- Running repeatable red, blue, and purple team scenarios
- Training SOC workflows without using customer data
- Checking that alerts include enough context for triage
- Producing simple evidence bundles and validation reports

## What this repo is not for

- Testing against public targets
- Storing real credentials, customer logs, or sensitive data
- Running malware, persistence, evasion, or destructive actions
- Replacing a production SIEM, EDR, or case-management platform

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .

greynoc-dmz run-scenario --scenario scenarios/auth-bruteforce-sim.json
greynoc-dmz validate-all

greynoc-dmz dashboard --host 127.0.0.1 --port 8787
```

Or run the local lab:

```bash
docker compose up --build
```

Open the dashboard:

```text
http://127.0.0.1:8787
```

## Planned layout

```text
apps/dashboard/              Web dashboard
configs/                     Lab settings
detections/rules/            Detection rules
docs/                        Design notes and team workflow guides
evidence/                    Generated evidence bundles, ignored by git
infra/local-lab/             Docker Compose lab services
reports/                     Generated reports, ignored by git
runbooks/                    Triage and response notes
scenarios/                   Repeatable validation scenarios
src/greynoc_dmz/             CLI, detection engine, reports, dashboard server
telemetry/fixtures/          Synthetic logs and events
tests/                       Unit and regression tests
```

## Validation flow

1. Select a scenario.
2. Replay the fixture telemetry.
3. Run the matching detections.
4. Compare expected alerts with actual alerts.
5. Save evidence.
6. Generate a report.
7. Tune and retest.

## Safety rules

Keep the lab isolated. Use owned systems or synthetic data only. Do not add real secrets, client data, production logs, or offensive tooling that can be used outside the lab.

## Repository

https://github.com/GreyNOC/DMZ
