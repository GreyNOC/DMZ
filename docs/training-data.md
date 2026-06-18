# Training-data export

GreyNOC DMZ turns every detection-validation scenario into a labeled record, so
a team can build a dataset for training or fine-tuning their own security AI
model. Each scenario added to the lab becomes another labeled example — DMZ as a
training-data factory.

## What a record contains

Each record is built from one scenario run:

- the synthetic telemetry window (the model input)
- the expected detection rules (the ground-truth label)
- the rules that actually fired, plus any missing or unexpected rules
- the alerts produced, with severity and host
- the pass/fail outcome
- an optional AI analysis note

## Formats

- `raw` — one JSON object per line with every field above. Flexible: transform
  it into whatever shape a training pipeline needs.
- `chat` — OpenAI-style fine-tuning JSON Lines. Each line is a `messages` array
  with a system prompt, a user message (telemetry plus the question), and an
  assistant message (the expected detections). Ready for chat-model fine-tuning.

## Commands

```bash
greynoc-dmz export-dataset                      # raw JSONL to datasets/dmz-dataset.jsonl
greynoc-dmz export-dataset --format chat        # OpenAI fine-tuning JSONL
greynoc-dmz export-dataset --out path/to.jsonl  # choose the output path
greynoc-dmz export-dataset --with-ai            # add a per-scenario AI analysis note
```

`--with-ai` needs a ready AI provider (see `docs/ai-providers.md`). It asks the
provider to review each scenario and stores the advisory note in every record.

## Notes

- Scenario data is synthetic. The dataset carries no customer telemetry.
- Generated datasets are written under `datasets/` and are not committed.
- The export does not write evidence or history files.
