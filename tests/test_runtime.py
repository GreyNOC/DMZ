from pathlib import Path

from greynoc_dmz.runtime import BUNDLED_LAB_DIR, is_lab_root, resolve_lab_root


def _make_lab_root(path: Path) -> Path:
    for name in ("configs", "detections", "scenarios", "telemetry"):
        (path / name).mkdir(parents=True)
        (path / name / "seed.txt").write_text(name, encoding="utf-8")
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


def test_resolve_lab_root_seeds_user_lab_from_frozen_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    bundle_lab = _make_lab_root(tmp_path / "bundle" / BUNDLED_LAB_DIR)
    monkeypatch.setattr("sys._MEIPASS", str(bundle_lab.parent), raising=False)
    monkeypatch.setenv("GREYNOC_DMZ_APP_DATA", str(tmp_path / "app-data"))

    root = resolve_lab_root(tmp_path / "empty")

    assert root == (tmp_path / "app-data" / "lab").resolve()
    assert (root / "detections" / "seed.txt").read_text(encoding="utf-8") == "detections"
