# Production readiness

GreyNOC DMZ is local-first by default. Before using it in a shared environment, complete this checklist.

## Required before shared use

- Enable authentication with `GREYNOC_DMZ_PASSWORD`.
- Run the dashboard behind TLS.
- Put a reverse proxy in front of the app.
- Restrict network access to trusted operators.
- Keep generated evidence and history out of git.
- Run `greynoc-dmz security-check` before every merge.
- Run `greynoc-dmz validate-all` before every release.
- Use synthetic telemetry unless a real system is approved in writing.

## Not ready for internet exposure

Do not expose the built-in Python dashboard directly to the public internet. It is intended for local lab use or controlled internal use behind proper infrastructure.

## Current controls

- Local optional authentication
- Session cookies
- Basic browser security headers
- Static HTML dashboard
- Synthetic telemetry fixtures
- Security marker scan
- CI validation
- Scheduled DMZ bot workflow

## Known gaps

- No OIDC or SSO integration yet
- No persistent user database yet
- No centralized audit backend yet
- No reverse proxy config yet
- No signed release artifacts yet
- No formal threat model document yet

## Release gate

A release candidate should not be tagged unless these commands pass:

```bash
ruff check .
mypy src
pytest
greynoc-dmz security-check
greynoc-dmz validate-all
```
