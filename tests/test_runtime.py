from pathlib import Path

from greynoc_dmz.runtime import is_lab_root, resolve_lab_root


def _make_lab_root(path: Path) -> Path:
    for name in ("configs", "detections", "scenarios", "telemetry"):
        (path / name).mkdir(parents=True)
    return path


def test_resolve_lab_root_prefers_valid_working_tree(tmp_path: Path) -> None:
    root = _make_lab_root(tmp_path)

    assert resolve_lab_root(root) == root.resolve()
    assert is_lab_root(root)


def test_resolve_lab_root_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    preferred = tmp_path / "preferred"
    preferred.mkdir()
    override = _make_lab_root(tmp_path / "override")
    monkeypatch.setenv("GREYNOC_DMZ_ROOT", str(override))

    assert resolve_lab_root(preferred) == override.resolve()
