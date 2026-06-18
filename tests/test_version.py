import tomllib
from pathlib import Path

from greynoc_dmz import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_project_metadata() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == data["project"]["version"]
