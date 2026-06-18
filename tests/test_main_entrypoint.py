import sys
import tomllib
from pathlib import Path

from greynoc_dmz import __main__

ROOT = Path(__file__).resolve().parents[1]


def test_main_launches_desktop_when_executable_has_no_args(monkeypatch) -> None:
    called = False

    def fake_launch_desktop() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(sys, "argv", ["greynoc-dmz.exe"])
    monkeypatch.setattr(__main__, "launch_desktop", fake_launch_desktop)

    __main__.main()

    assert called


def test_console_script_uses_main_entrypoint() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["greynoc-dmz"] == "greynoc_dmz.__main__:main"
