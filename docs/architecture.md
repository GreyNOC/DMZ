# Architecture

GreyNOC DMZ has four parts.

1. Scenarios describe the test case and expected rule IDs.
2. Telemetry fixtures provide synthetic events.
3. Detection rules match events and create alerts.
4. Reports and evidence files show what fired and what missed.

The first version is intentionally small. The detection engine is local and deterministic so test results are repeatable.

Future integrations should be adapters. Keep the core engine independent from any one SIEM, EDR, or ticketing system.
