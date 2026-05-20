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
    "password=": "hard-coded password marker",
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

SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip"}


def scan_repo(root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(root))
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            for pattern, reason in DENY_PATTERNS.items():
                if pattern.lower() in lowered:
                    findings.append(SecurityFinding(relative, index, reason))
    return findings
