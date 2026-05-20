# Operator guide

Use `greynoc-dmz validate-all` before changing detection rules and after each change.

A scenario passes when every expected rule fires and no unexpected rule fires.

A scenario fails when:

- an expected rule does not fire
- a rule fires when it should not
- telemetry cannot be parsed
- a rule file is invalid

Reports are written to `reports/`. Evidence files are written to `evidence/`.
