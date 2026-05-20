# Integrations

GreyNOC DMZ supports a vendor-neutral integration layer. The first pass defines connector types and readiness checks. Vendor-specific adapters should build on this layer.

## Integration types

- SIEM: receive alerts or publish scenario results
- EDR: receive endpoint context or publish validation findings
- Ticketing: create or update work items from failed scenarios
- Cloud: pull audit-style events or publish validation metadata

## Supported first targets

These are planned targets, not enabled by default:

- Splunk-compatible SIEM
- Elastic-compatible SIEM
- Wazuh-compatible SIEM
- Microsoft Defender-compatible EDR
- Jira-compatible ticketing
- GitHub Issues-compatible ticketing
- AWS audit-event style sources
- Azure audit-event style sources
- Google Cloud audit-event style sources

## Safety rules

- Keep credentials out of git.
- Store credential references in environment variables or a secret manager.
- Use synthetic data for tests.
- Use allowlisted lab endpoints before connecting to real systems.
- Do not send customer data to a test integration.
- Log only connector status, not credential values.

## Current commands

```bash
greynoc-dmz integration-check
```

The command reports whether built-in placeholder integrations are disabled, missing config, or ready.

## Adapter design

Adapters should implement one of these interfaces:

- `AlertSink`
- `ScenarioPublisher`

Keep adapter code small. The core engine should not depend on a specific SIEM, EDR, ticketing system, or cloud provider.
