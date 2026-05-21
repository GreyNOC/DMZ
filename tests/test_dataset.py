import json
from pathlib import Path

from greynoc_dmz.dataset import DatasetFormat, build_dataset, run_lab, write_dataset

ROOT = Path(__file__).resolve().parents[1]


def test_run_lab_loads_every_scenario() -> None:
    runs = run_lab(ROOT)

    assert len(runs) >= 3
    for run in runs:
        assert run.events
        assert run.result.scenario_id == run.scenario.id


def test_raw_dataset_record_shape() -> None:
    runs = run_lab(ROOT)

    records = build_dataset(runs, DatasetFormat.raw)

    assert len(records) == len(runs)
    first = records[0]
    assert first["telemetry"]
    assert "expected_rules" in first
    assert "passed" in first
    assert first["ai_analysis"] is None


def test_chat_dataset_is_openai_shaped() -> None:
    runs = run_lab(ROOT)

    records = build_dataset(runs, DatasetFormat.chat)

    assert len(records) == len(runs)
    for record in records:
        messages = record["messages"]
        assert isinstance(messages, list)
        assert [message["role"] for message in messages] == ["system", "user", "assistant"]


def test_chat_user_message_includes_telemetry() -> None:
    runs = run_lab(ROOT)

    records = build_dataset(runs, DatasetFormat.chat)
    user_message = records[0]["messages"][1]["content"]

    assert "telemetry" in user_message.lower()


def test_ai_notes_appear_in_records() -> None:
    runs = run_lab(ROOT)
    notes = {run.scenario.id: f"note for {run.scenario.id}" for run in runs}

    raw = build_dataset(runs, DatasetFormat.raw, ai_notes=notes)
    assert raw[0]["ai_analysis"] == f"note for {runs[0].scenario.id}"

    chat = build_dataset(runs, DatasetFormat.chat, ai_notes=notes)
    assistant_message = chat[0]["messages"][2]["content"]
    assert "Analyst notes:" in assistant_message


def test_write_dataset_writes_valid_jsonl(tmp_path: Path) -> None:
    runs = run_lab(ROOT)
    records = build_dataset(runs, DatasetFormat.raw)

    path = write_dataset(records, tmp_path / "out" / "dataset.jsonl")

    assert path.exists()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(records)
    for line in lines:
        json.loads(line)
