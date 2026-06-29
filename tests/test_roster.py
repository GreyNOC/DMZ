import json
from pathlib import Path

from greynoc_dmz.ai import AIReadinessStatus, check_fighter_readiness, find_fighter, load_roster

ROOT = Path(__file__).resolve().parents[1]


def _write_roster(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "fighters": [
                    {
                        "name": "Claude",
                        "provider": "anthropic",
                        "model": "claude-opus-4-8",
                        "token_env": "ANTHROPIC_API_KEY",
                        "max_tokens": 2048,
                    },
                    {
                        "name": "Local",
                        "provider": "openai_compatible",
                        "model": "llama3.1",
                        "base_url": "http://127.0.0.1:11434/v1",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def test_load_roster_parses_fighters(tmp_path: Path) -> None:
    path = tmp_path / "roster.json"
    _write_roster(path)

    roster = load_roster(path)

    assert [fighter.name for fighter in roster] == ["Claude", "Local"]
    claude = find_fighter(roster, "claude")
    assert claude is not None
    assert claude.provider == "anthropic"
    assert claude.max_tokens == 2048


def test_to_config_threads_allow_external(tmp_path: Path) -> None:
    path = tmp_path / "roster.json"
    _write_roster(path)
    claude = find_fighter(load_roster(path), "Claude")
    assert claude is not None

    config = claude.to_config(allow_external=True)

    assert config.enabled is True
    assert config.allow_external is True
    assert config.provider == "anthropic"
    assert config.max_tokens == 2048


def test_missing_roster_returns_empty(tmp_path: Path) -> None:
    assert load_roster(tmp_path / "nope.json") == []


def test_malformed_roster_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "roster.json"
    path.write_text("[]", encoding="utf-8")
    assert load_roster(path) == []


def test_local_fighter_is_ready(tmp_path: Path) -> None:
    path = tmp_path / "roster.json"
    _write_roster(path)
    local = find_fighter(load_roster(path), "Local")
    assert local is not None

    assert check_fighter_readiness(local).status == AIReadinessStatus.ready


def test_malformed_int_fields_degrade_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "roster.json"
    path.write_text(
        json.dumps(
            {
                "fighters": [
                    {
                        "name": "X",
                        "provider": "openai_compatible",
                        "model": "m",
                        "base_url": "http://127.0.0.1:1/v1",
                        "max_tokens": "--5",
                        "timeout_seconds": "oops",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    roster = load_roster(path)

    assert len(roster) == 1
    assert roster[0].max_tokens == 1024
    assert roster[0].timeout_seconds == 30


def test_committed_example_roster_is_valid() -> None:
    roster = load_roster(ROOT / "configs" / "ai-roster.json")

    names = {fighter.name for fighter in roster}
    assert {"Claude", "GPT", "Gemini"} <= names
    providers = {fighter.provider for fighter in roster}
    assert providers <= {"anthropic", "openai_compatible", "gemini"}
    for fighter in roster:
        assert fighter.model, f"{fighter.name} is missing a model"
