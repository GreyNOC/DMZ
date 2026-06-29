from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

_TRUE_VALUES = {"1", "true", "yes", "on"}


class EndpointScope(StrEnum):
    local = "local"
    private = "private"
    external = "external"


@dataclass(frozen=True)
class SafetyPolicy:
    """Controls whether integration traffic may leave the local lab.

    Local and private endpoints are always allowed. External endpoints are
    blocked unless ``allow_external`` is set or the host is on ``allowlist``.
    """

    allow_external: bool
    allowlist: frozenset[str]


@dataclass(frozen=True)
class EndpointVerdict:
    allowed: bool
    scope: EndpointScope
    host: str
    reason: str


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def load_safety_policy() -> SafetyPolicy:
    """Build the safety policy from environment variables."""
    raw_allowlist = os.environ.get("GREYNOC_DMZ_INTEGRATION_ALLOWLIST", "")
    allowlist = frozenset(item.strip().lower() for item in raw_allowlist.split(",") if item.strip())
    return SafetyPolicy(
        allow_external=_env_flag("GREYNOC_DMZ_ALLOW_EXTERNAL"),
        allowlist=allowlist,
    )


def classify_host(host: str) -> EndpointScope:
    """Classify a hostname or IP as a local, private, or external endpoint."""
    if host.lower() == "localhost":
        return EndpointScope.local
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return EndpointScope.external
    if address.is_loopback:
        return EndpointScope.local
    # Link-local includes the cloud metadata range (169.254.169.254, fd00:ec2::254).
    # Treat it as external so it requires explicit allowance instead of being a
    # trusted lab endpoint — closing an SSRF-to-metadata path.
    if address.is_link_local:
        return EndpointScope.external
    if address.is_private:
        return EndpointScope.private
    return EndpointScope.external


def check_endpoint(url: str, policy: SafetyPolicy) -> EndpointVerdict:
    """Decide whether an integration may send to ``url`` under ``policy``."""
    host = urlparse(url).hostname or ""
    if not host:
        return EndpointVerdict(False, EndpointScope.external, host, "endpoint has no host")

    scope = classify_host(host)
    if scope in {EndpointScope.local, EndpointScope.private}:
        return EndpointVerdict(True, scope, host, f"{scope.value} lab endpoint")
    if host.lower() in policy.allowlist:
        return EndpointVerdict(True, scope, host, "host is on the integration allowlist")
    if policy.allow_external:
        return EndpointVerdict(True, scope, host, "external endpoint allowed by policy")
    return EndpointVerdict(
        False,
        scope,
        host,
        "external endpoint blocked: set GREYNOC_DMZ_ALLOW_EXTERNAL=1 "
        "or add the host to GREYNOC_DMZ_INTEGRATION_ALLOWLIST",
    )
