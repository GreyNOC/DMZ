from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecurityFinding:
    path: str
    line: int
    reason: str


DENY_PATTERNS = {
    "BEGIN RSA PRIVATE KEY": "private key material",
    "BEGIN OPENSSH PRIVATE KEY": "private key material",
    "aws_secret_access_key": "cloud secret marker",
    "passwd=": "hard-coded password marker",
    "curl http://": "plain HTTP shell download pattern",
    "wget http://": "plain HTTP shell download pattern",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}

SKIP_PATH_PARTS = {
    "tests",
    "src/greynoc_dmz.egg-info",
}

SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip"}
SELF_PATH = "src/greynoc_dmz/security.py"


def _should_skip(path: Path, relative: str) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if relative == SELF_PATH:
        return True
    return any(relative == item or relative.startswith(f"{item}/") for item in SKIP_PATH_PARTS)


def _has_password_assignment(line: str) -> bool:
    stripped = line.strip().lower()
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    return stripped.startswith(("password=", "passwd="))


def scan_repo(root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if _should_skip(path, relative):
            continue

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            if _has_password_assignment(line):
                findings.append(SecurityFinding(relative, index, "hard-coded password marker"))
                continue
            for pattern, reason in DENY_PATTERNS.items():
                if pattern.lower() in lowered:
                    findings.append(SecurityFinding(relative, index, reason))
    return findings
