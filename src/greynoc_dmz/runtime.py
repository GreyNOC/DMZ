from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REQUIRED_LAB_DIRS = ("configs", "detections", "scenarios", "telemetry")
LAB_ASSET_DIRS = (*REQUIRED_LAB_DIRS, "runbooks")
BUNDLED_LAB_DIR = "greynoc_dmz_lab"
APP_DATA_ENV = "GREYNOC_DMZ_APP_DATA"


def is_lab_root(path: Path) -> bool:
    return all((path / name).exists() for name in REQUIRED_LAB_DIRS)


def user_data_dir() -> Path:
    override = os.environ.get(APP_DATA_ENV)
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "GreyNOC" / "DMZ"
    return Path.home() / ".greynoc" / "dmz"


def _copy_missing_tree(source: Path, target: Path) -> None:
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def ensure_user_lab_root(seed_root: Path) -> Path:
    target = user_data_dir() / "lab"
    target.mkdir(parents=True, exist_ok=True)
    for name in LAB_ASSET_DIRS:
        source = seed_root / name
        if source.exists():
            _copy_missing_tree(source, target / name)
    return target


def resolve_lab_root(preferred: Path | None = None) -> Path:
    """Find the lab root for source checkouts, installs, and frozen binaries."""
    candidates: list[Path] = []

    env_root = os.environ.get("GREYNOC_DMZ_ROOT")
    if env_root:
        candidates.append(Path(env_root))

    if preferred is not None:
        candidates.append(preferred)

    candidates.append(Path(sys.executable).resolve().parent)

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundled_lab = Path(bundle_root) / BUNDLED_LAB_DIR
        if is_lab_root(bundled_lab):
            return ensure_user_lab_root(bundled_lab).resolve()

    candidates.append(Path(__file__).resolve().parents[2])

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if is_lab_root(resolved):
            return resolved

    return (preferred or Path.cwd()).resolve()
