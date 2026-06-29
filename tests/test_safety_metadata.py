from greynoc_dmz.integrations.safety import (
    EndpointScope,
    SafetyPolicy,
    check_endpoint,
    classify_host,
)


def test_link_local_metadata_ip_is_external() -> None:
    # The cloud metadata IP lives in the link-local range and must NOT be treated
    # as a trusted private lab endpoint.
    assert classify_host("169.254.169.254") == EndpointScope.external


def test_ipv6_link_local_is_external() -> None:
    assert classify_host("fe80::1") == EndpointScope.external


def test_metadata_endpoint_blocked_without_allowance() -> None:
    verdict = check_endpoint(
        "http://169.254.169.254/latest/meta-data/",
        SafetyPolicy(allow_external=False, allowlist=frozenset()),
    )

    assert not verdict.allowed
    assert verdict.scope == EndpointScope.external
