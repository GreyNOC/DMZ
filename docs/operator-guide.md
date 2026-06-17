# Operator guide

Use `greynoc-dmz validate-all` before changing detection rules and after each change.

Run `greynoc-dmz lint` after editing any rule or scenario. It catches duplicate
ids, missing runbooks, malformed MITRE ids, and broken match expressions before
they reach validation.

Run `greynoc-dmz coverage` to see which MITRE ATT&CK tactics your rules cover and
where the gaps are.

A scenario passes when every expected rule fires and no unexpected rule fires.

A scenario fails when:

- an expected rule does not fire
- a rule fires when it should not
- telemetry cannot be parsed
- a rule file is invalid

Reports are written to `reports/`. Evidence files are written to `evidence/`.
