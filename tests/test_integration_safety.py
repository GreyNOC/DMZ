from greynoc_dmz.integrations import (
    EndpointScope,
    SafetyPolicy,
    check_endpoint,
    classify_host,
)

_NO_EXTERNAL = SafetyPolicy(allow_external=False, allowlist=frozenset())


def test_localhost_is_local() -> None:
    assert classify_host("localhost") == EndpointScope.local
    assert classify_host("127.0.0.1") == EndpointScope.local


def test_private_ranges_are_private() -> None:
    assert classify_host("10.1.2.3") == EndpointScope.private
    assert classify_host("192.168.1.10") == EndpointScope.private


def test_public_host_is_external() -> None:
    assert classify_host("splunk.example.invalid") == EndpointScope.external


def test_local_endpoint_is_allowed() -> None:
    verdict = check_endpoint("http://127.0.0.1:8088/services/collector", _NO_EXTERNAL)

    assert verdict.allowed is True
    assert verdict.scope == EndpointScope.local


def test_private_endpoint_is_allowed() -> None:
    verdict = check_endpoint("https://10.0.0.5/dmz-hook", _NO_EXTERNAL)

    assert verdict.allowed is True
    assert verdict.scope == EndpointScope.private


def test_external_endpoint_is_blocked_by_default() -> None:
    verdict = check_endpoint("https://splunk.example.invalid:8088", _NO_EXTERNAL)

    assert verdict.allowed is False
    assert verdict.scope == EndpointScope.external


def test_external_endpoint_allowed_when_policy_permits() -> None:
    policy = SafetyPolicy(allow_external=True, allowlist=frozenset())

    verdict = check_endpoint("https://splunk.example.invalid:8088", policy)

    assert verdict.allowed is True


def test_external_endpoint_allowed_by_allowlist() -> None:
    policy = SafetyPolicy(allow_external=False, allowlist=frozenset({"splunk.example.invalid"}))

    verdict = check_endpoint("https://splunk.example.invalid:8088", policy)

    assert verdict.allowed is True
