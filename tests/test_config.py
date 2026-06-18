import json
from pathlib import Path

from greynoc_dmz.config import load_lab_config


def test_load_lab_config_defaults_when_missing(tmp_path: Path) -> None:
    config = load_lab_config(tmp_path)

    assert config.report_dir == "reports"
    assert config.evidence_dir == "evidence"


def test_load_lab_config_reads_aliased_fields_and_ignores_extras(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "lab.json").write_text(
        json.dumps(
            {
                "name": "Lab",
                "environment": "local",
                "default_report_dir": "out/reports",
                "default_evidence_dir": "out/evidence",
                "allowed_modes": ["synthetic"],
                "deny_public_targets": True,
            }
        ),
        encoding="utf-8",
    )

    config = load_lab_config(tmp_path)

    assert config.name == "Lab"
    assert config.report_dir == "out/reports"
    assert config.evidence_dir == "out/evidence"
