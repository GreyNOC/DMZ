# Safety rules

GreyNOC DMZ uses synthetic telemetry by default. Keep it that way unless a real system is approved in writing and isolated from production.

Allowed:

- Synthetic logs
- Private lab IP ranges
- Local Docker services
- Benign replay of fixture events
- Rule validation and report generation

Not allowed in this repo:

- Real credentials or tokens
- Customer data
- Production logs
- Malware samples
- Persistence, evasion, or destructive test code
- Instructions for attacking third-party systems

When in doubt, use a fixture instead of live activity.
