# GreyNOC DMZ

GreyNOC DMZ is a safe, branded Detection Management Zone for validating GreyNOC red, blue, and purple team workflows in an isolated lab.

It is built for defensive testing, detection engineering, operator training, and repeatable evidence collection. The starter repo uses synthetic telemetry and harmless local services so detections can be tested without touching production systems, customer data, or public targets.

## Tagline

Break safely. Detect clearly. Improve continuously.

## What this repo includes

- Safe cyber-range starter layout
- Docker Compose lab network
- GreyNOC-branded dashboard stub
- Synthetic telemetry fixtures
- Detection rules in JSON
- Scenario definitions mapped to MITRE ATT&CK-style tactics
- Detection validation runner
- Evidence and report generation
- Red, blue, and purple team workflow docs
- Safety boundaries for public/demo use

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .

greynoc-dmz run-scenario --scenario scenarios/auth-bruteforce-sim.json
greynoc-dmz validate-all

greynoc-dmz dashboard --host 127.0.0.1 --port 8787
```

Or run with Docker Compose:

```bash
docker compose up --build
```

Then open:

```text
http://127.0.0.1:8787
```

## Repo layout

```text
apps/dashboard/              GreyNOC DMZ browser dashboard
configs/                     Lab configuration
detections/                  Detection rules
  rules/                     JSON detection rules
docs/                        Red/blue/purple guides and safety docs
evidence/                    Generated evidence bundles, ignored by git
infra/local-lab/             Docker Compose lab services
reports/                     Generated reports, ignored by git
runbooks/                    Operator response runbooks
scenarios/                   Repeatable validation scenarios
src/greynoc_dmz/             Python CLI, engine, dashboard, reports
telemetry/fixtures/          Synthetic logs and events
tests/                       Unit tests
```

## Safety model

GreyNOC DMZ is for owned, approved, or fully synthetic environments only.

This starter repo does not include exploitation code, credential attacks, malware, bypasses, persistence, evasion, destructive actions, or instructions for targeting third-party systems. Red-team simulations are represented as synthetic logs/events and benign local requests designed to validate detections.

## Core workflow

1. Choose a scenario.
2. Replay synthetic telemetry.
3. Run detections.
4. Confirm expected alerts fired.
5. Collect evidence.
6. Generate a report.
7. Tune rules and retest.

## GitHub

Repository: https://github.com/GreyNOC/DMZ
