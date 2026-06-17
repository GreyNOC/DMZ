from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .io import read_json


class LabConfig(BaseModel):
    """Lab-level settings loaded from ``configs/lab.json``.

    Unknown keys (for example ``allowed_modes`` or ``deny_public_targets``) are
    accepted and ignored so the file can carry documentation-only fields.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = "GreyNOC DMZ"
    environment: str = "local"
    report_dir: str = Field(default="reports", alias="default_report_dir")
    evidence_dir: str = Field(default="evidence", alias="default_evidence_dir")


def load_lab_config(root: Path) -> LabConfig:
    path = root / "configs" / "lab.json"
    if not path.exists():
        return LabConfig()
    return LabConfig.model_validate(read_json(path))
