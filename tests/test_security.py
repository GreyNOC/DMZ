from pathlib import Path

from greynoc_dmz.security import scan_repo


def test_security_scan_flags_secret_markers(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.env"
    bad_file.write_text("password=not-a-real-secret\n", encoding="utf-8")

    findings = scan_repo(tmp_path)

    assert len(findings) == 1
    assert findings[0].path == "bad.env"
    assert findings[0].reason == "hard-coded password marker"


def test_security_scan_passes_clean_repo(tmp_path: Path) -> None:
    clean_file = tmp_path / "README.md"
    clean_file.write_text("# clean\n", encoding="utf-8")

    findings = scan_repo(tmp_path)

    assert findings == []
