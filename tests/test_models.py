import pytest
from pydantic import ValidationError

from greynoc_dmz.models import DetectionRule


def test_rule_ids_use_gnoc_prefix() -> None:
    with pytest.raises(ValidationError):
        DetectionRule(
            id="BAD-001",
            name="bad",
            description="bad",
            severity="low",
            data_source="auth",
        )
