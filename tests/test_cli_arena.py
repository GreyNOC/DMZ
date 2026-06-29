import json
from pathlib import Path

from conftest import RecordingServer
from typer.testing import CliRunner

from greynoc_dmz.cli import app

runner = CliRunner()


def _openai_reply(content: str) -> str:
    return json.dumps({"model": "m", "choices": [{"message": {"content": content}}]})


def _local_roster(path: Path, port: int, *, extra: list[dict[str, object]] | None = None) -> None:
    fighters: list[dict[str, object]] = [
        {
            "name": name,
            "provider": "openai_compatible",
            "model": "m",
            "base_url": f"http://127.0.0.1:{port}/v1",
        }
        for name in ("Alpha", "Beta", "Judge")
    ]
    if extra:
        fighters.extend(extra)
    path.write_text(json.dumps({"fighters": fighters}), encoding="utf-8")


def test_ai_roster_lists_fighters(tmp_path: Path, recording_server: RecordingServer) -> None:
    roster = tmp_path / "roster.json"
    _local_roster(roster, recording_server.server_address[1])

    result = runner.invoke(app, ["ai-roster", "--roster", str(roster)])

    assert result.exit_code == 0
    assert "Alpha" in result.output
    assert "openai_compatible" in result.output


def test_live_battle_runs_and_emits_json(tmp_path: Path, recording_server: RecordingServer) -> None:
    recording_server.reply_body = _openai_reply(
        json.dumps({"scores": {"Alpha": 8, "Beta": 5}, "winner": "Alpha", "rationale": "alpha"})
    )
    roster = tmp_path / "roster.json"
    _local_roster(roster, recording_server.server_address[1])

    result = runner.invoke(
        app,
        [
            "live-battle",
            "--roster",
            str(roster),
            "--fighters",
            "Alpha,Beta",
            "--judge",
            "Judge",
            "--rounds",
            "1",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"winner": "Alpha"' in result.output
    assert '"mode": "live"' in result.output


def test_collab_battle_runs(tmp_path: Path, recording_server: RecordingServer) -> None:
    recording_server.reply_body = _openai_reply(
        json.dumps({"scores": {"Red": 9, "Blue": 4}, "winner": "Red", "rationale": "red"})
    )
    roster = tmp_path / "roster.json"
    _local_roster(roster, recording_server.server_address[1])

    result = runner.invoke(
        app,
        [
            "collab-battle",
            "--roster",
            str(roster),
            "--teams",
            "Red=Alpha;Blue=Beta",
            "--judge",
            "Judge",
            "--rounds",
            "1",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"winner": "Red"' in result.output
    assert '"mode": "collaborative"' in result.output


def test_live_battle_gates_unready_external_fighter(
    tmp_path: Path, recording_server: RecordingServer
) -> None:
    roster = tmp_path / "roster.json"
    _local_roster(
        roster,
        recording_server.server_address[1],
        extra=[
            {
                "name": "Claude",
                "provider": "anthropic",
                "model": "claude-opus-4-8",
                "token_env": "CLI_TEST_MISSING_KEY",
            }
        ],
    )

    result = runner.invoke(
        app,
        ["live-battle", "--roster", str(roster), "--fighters", "Alpha,Claude", "--rounds", "1"],
    )

    assert result.exit_code == 1
    assert "Claude" in result.output


def test_live_battle_default_judge_runs(tmp_path: Path, recording_server: RecordingServer) -> None:
    # No --judge given: the third roster fighter (not a combatant) judges.
    recording_server.reply_body = _openai_reply(
        json.dumps({"scores": {"Alpha": 6, "Beta": 9}, "winner": "Beta"})
    )
    roster = tmp_path / "roster.json"
    _local_roster(roster, recording_server.server_address[1])

    result = runner.invoke(
        app,
        ["live-battle", "--roster", str(roster), "--fighters", "Alpha,Beta", "--rounds", "1", "--json"],
    )

    assert result.exit_code == 0
    assert '"judge": "Judge"' in result.output
    assert '"winner": "Beta"' in result.output


def test_live_battle_rejects_duplicate_fighters(
    tmp_path: Path, recording_server: RecordingServer
) -> None:
    roster = tmp_path / "roster.json"
    _local_roster(roster, recording_server.server_address[1])

    result = runner.invoke(
        app, ["live-battle", "--roster", str(roster), "--fighters", "Alpha,Alpha", "--rounds", "1"]
    )

    assert result.exit_code != 0
    assert "duplicate" in result.output.lower()


def test_live_battle_gates_unready_external_judge(
    tmp_path: Path, recording_server: RecordingServer
) -> None:
    roster = tmp_path / "roster.json"
    _local_roster(
        roster,
        recording_server.server_address[1],
        extra=[
            {
                "name": "Claude",
                "provider": "anthropic",
                "model": "claude-opus-4-8",
                "token_env": "CLI_TEST_MISSING_KEY",
            }
        ],
    )

    result = runner.invoke(
        app,
        [
            "live-battle",
            "--roster",
            str(roster),
            "--fighters",
            "Alpha,Beta",
            "--judge",
            "Claude",
            "--rounds",
            "1",
        ],
    )

    assert result.exit_code == 1
    assert "Claude" in result.output
    assert "--allow-external" in result.output


def test_live_battle_reports_empty_roster(tmp_path: Path) -> None:
    result = runner.invoke(app, ["live-battle", "--roster", str(tmp_path / "missing.json")])

    assert result.exit_code == 1
    assert "no fighters" in result.output.lower()
