from __future__ import annotations

import re
from typing import Any

# Supported structured operators. A rule match value may be:
#   - a scalar string   -> case-insensitive substring ("contains")
#   - a list            -> membership ("in")
#   - {"op": ..., "value": ..., "negate": bool}  -> structured operator
OPERATORS = {
    "equals",
    "eq",
    "contains",
    "startswith",
    "endswith",
    "regex",
    "in",
    "gt",
    "gte",
    "lt",
    "lte",
}

_NUMERIC_OPS = {"gt", "gte", "lt", "lte"}


class MatchError(ValueError):
    """Raised when a rule's match expression is malformed."""


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply(op: str, actual: Any, expected: Any) -> bool:
    if op in {"equals", "eq"}:
        return bool(actual == expected)
    if op == "contains":
        return isinstance(actual, str) and isinstance(expected, str) and expected.lower() in actual.lower()
    if op == "startswith":
        return isinstance(actual, str) and isinstance(expected, str) and actual.lower().startswith(expected.lower())
    if op == "endswith":
        return isinstance(actual, str) and isinstance(expected, str) and actual.lower().endswith(expected.lower())
    if op == "regex":
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        return re.search(expected, actual) is not None
    if op == "in":
        if not isinstance(expected, list):
            raise MatchError("'in' operator requires a list value")
        return actual in expected
    if op in _NUMERIC_OPS:
        left = _as_number(actual)
        right = _as_number(expected)
        if left is None or right is None:
            return False
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        return left <= right
    raise MatchError(f"unknown match operator: {op!r}")


def value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict) and "op" in expected:
        op = str(expected["op"]).lower()
        result = _apply(op, actual, expected.get("value"))
        return (not result) if bool(expected.get("negate", False)) else result
    if isinstance(expected, list):
        return actual in expected
    if isinstance(actual, str) and isinstance(expected, str):
        return expected.lower() in actual.lower()
    return bool(actual == expected)
