import sys

from greynoc_dmz import __main__


def test_main_launches_desktop_when_executable_has_no_args(monkeypatch) -> None:
    called = False

    def fake_launch_desktop() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(sys, "argv", ["greynoc-dmz.exe"])
    monkeypatch.setattr(__main__, "launch_desktop", fake_launch_desktop)

    __main__.main()

    assert called
