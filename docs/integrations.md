# Integrations

GreyNOC DMZ publishes detection-validation results into the security tooling a
team already runs. Integrations are small vendor-neutral adapters; the core
validation engine never imports a vendor SDK.

## How it works

1. `validate-all` produces a `ScenarioResult` for every scenario.
2. `integration-publish` loads `configs/integrations.json`.
3. Every enabled, ready integration receives each result through its adapter.
4. An endpoint safety gate runs before any network call.

## Integration kinds

- `siem` — forward validation results to a SIEM
- `edr` — forward results to an EDR/XDR or SOAR pipeline
- `ticketing` — open work items from failed scenarios
- `cloud` — publish validation metadata to a cloud destination
- `file` — write results to a local file (no network)

## Built-in adapters

| Adapter | Target | Auth | Notes |
|---|---|---|---|
| `file` | Local NDJSON feed | none | Safe default. Appends to `evidence/integration-outbox.ndjson`. |
| `webhook` | Any JSON HTTP endpoint | bearer token | MSP dashboards, SOAR, EDR/XDR intake, chat. |
| `splunk_hec` | Splunk HTTP Event Collector | HEC token | One event per scenario result. |
| `jira` | Jira issue creation | email + API token | Opens a ticket only when a scenario fails. |

New adapters register themselves with the `@register` decorator in
`src/greynoc_dmz/integrations/adapters.py`. Adding one needs no core change.

## Configuration

Integrations are defined in `configs/integrations.json`. The file is safe to
commit: it references credentials only by environment-variable name and never
holds a secret.

```json
{
  "integrations": [
    {
      "name": "soc-webhook",
      "kind": "edr",
      "adapter": "webhook",
      "enabled": true,
      "base_url": "https://events.example.net/greynoc-dmz",
      "token_env": "DMZ_WEBHOOK_TOKEN"
    }
  ]
}
```

The secret itself is supplied at runtime through the named environment variable
and is set outside git. Adapter-specific settings go under `options` (for
example the Jira `project` and `email`, or the Splunk `index`).

## Safety model

- Integrations are disabled by default.
- Local and private endpoints are always allowed.
- External endpoints are blocked unless `GREYNOC_DMZ_ALLOW_EXTERNAL=1` is set,
  or the host is listed in `GREYNOC_DMZ_INTEGRATION_ALLOWLIST`.
- `integration-publish` runs as a dry run unless `--send` is passed.
- Credentials are read from the environment at send time and are never logged.
- Use synthetic scenario data; do not point integrations at customer systems
  for routine validation.

## Commands

```bash
greynoc-dmz integration-check            # show configured integrations
greynoc-dmz integration-publish          # dry run: preview what would be sent
greynoc-dmz integration-publish --send   # transmit to every ready integration
```

## Planned

- Inbound telemetry adapters (pull real EDR/SIEM events into fixtures)
- Provider-specific EDR adapters (Microsoft Defender, CrowdStrike)
- Elastic and Wazuh SIEM adapters
