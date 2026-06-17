import pytest

from greynoc_dmz.matching import MatchError, value_matches


def test_scalar_string_is_case_insensitive_contains() -> None:
    assert value_matches("GET /login failed LOGIN", "failed login") is True
    assert value_matches("ok", "failed") is False


def test_list_is_membership() -> None:
    assert value_matches("POST", ["GET", "POST"]) is True
    assert value_matches("DELETE", ["GET", "POST"]) is False


def test_equals_operator() -> None:
    assert value_matches("root", {"op": "equals", "value": "root"}) is True
    assert value_matches("root", {"op": "eq", "value": "admin"}) is False


def test_regex_operator() -> None:
    assert value_matches("q=union   select 1", {"op": "regex", "value": r"union\s+select"}) is True
    assert value_matches("union", {"op": "regex", "value": r"union\s+select"}) is False


def test_numeric_operators_coerce_strings() -> None:
    assert value_matches("500", {"op": "gte", "value": 400}) is True
    assert value_matches(200, {"op": "gte", "value": 400}) is False
    assert value_matches("not-a-number", {"op": "lt", "value": 5}) is False


def test_negate_flips_result() -> None:
    assert value_matches("admin", {"op": "equals", "value": "admin", "negate": True}) is False
    assert value_matches("user", {"op": "equals", "value": "admin", "negate": True}) is True


def test_startswith_endswith() -> None:
    assert value_matches("/etc/shadow", {"op": "startswith", "value": "/etc"}) is True
    assert value_matches("file.exe", {"op": "endswith", "value": ".EXE"}) is True


def test_unknown_operator_raises() -> None:
    with pytest.raises(MatchError):
        value_matches("x", {"op": "wat", "value": "x"})
