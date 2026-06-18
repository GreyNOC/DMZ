from __future__ import annotations

import os
import sys
from pathlib import Path

REQUIRED_LAB_DIRS = ("configs", "detections", "scenarios", "telemetry")
BUNDLED_LAB_DIR = "greynoc_dmz_lab"


def is_lab_root(path: Path) -> bool:
    return all((path / name).exists() for name in REQUIRED_LAB_DIRS)


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
        candidates.append(Path(bundle_root) / BUNDLED_LAB_DIR)

    candidates.append(Path(__file__).resolve().parents[2])

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if is_lab_root(resolved):
            return resolved

    return (preferred or Path.cwd()).resolve()
