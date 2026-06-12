# Pipeline Workflows

Local-first workflow packets for David's AI/NLP/FORGE/Brain system.

This repo holds the programmable parts of the pipeline:

- engine runtime
- folder contracts
- station source code
- prompts
- preference profiles
- launchers
- schemas
- setup and troubleshooting scripts
- small test fixtures
- CLI partner operating patterns
- production vault output specs

This repo does **not** hold the local model brain:

- no NLP model weights
- no Ollama/Hugging Face model folders
- no vector indexes
- no private vault dumps
- no runtime databases
- no secrets

## Mental Model

The station graph is the internal machine room. The consumer-facing workflow is a simple packet:

```text
PROCESS_NAME/
  INPUT/
  OUTPUT/
  REVIEW/
  ARCHIVE/
  ERROR/
  CONFIG/
  PREFS/
  PROMPTS/
  SCRIPTS/
  LOGS/
  RUN_PIPELINE.bat
  RUN_THIS_STAGE.bat
  TROUBLESHOOT.bat
  README.md
```

Each packet can either run a full pipeline or stop at one station.

## Stages

- Intake: classify, identify, detect format, deduplicate
- Transform: clean, extract, vectorize, build HTML, render TTS, create thumbnails
- Validate: grade, audit, map axioms, cross-check
- Route: vault drop, R2 publish, Substack queue, Postgres warehouse, NAS archive
- Signals: gap, duplicate, quality, ready, upstream

## Engine Layer

The working Python engine imported from `D:\BIL` lives under `engines/`.

- `engines/pipeline/station_base.py`: station base classes, manifests, signals
- `engines/pipeline/pipeline_engine.py`: watcher, registry, routing, logging
- `engines/pipeline/llm_hub.py`: queued LLM checkpoint layer
- `engines/pipeline/stations/classifier.py`: working Station 1
- `engines/pipeline/stations/media_transformer.py`: working Station 2

See `docs/engine-import-map.md`.

## LLM Checkpoints

Each stage can have a large language model checkpoint:

- Intake LLM: what is this and where should it go?
- Transform LLM: what should be extracted, cleaned, or converted?
- Validate LLM: did it pass the gate?
- Route LLM: where should the result land?
- Signal LLM: what should the system ask upstream?

## Preference Layer

The preference layer is the control surface above the stations. It says how a
workflow should behave before any station starts:

- which model lane to use
- whether to run fast, strong, or backup mode
- how aggressively to clean speech-to-text text
- whether to stop for review or keep routing
- where outputs should land
- how much detail David wants in summaries

Global defaults live in `preferences/defaults.json`. Workflow packets can
override them in `workflows/PROCESS_NAME/PREFS/preferences.json`.

## Claude CLI Pattern

For folder reorganization or vault compilation, Claude CLI should run the
inventory protocol before changing files:

1. inventory source folders
2. hash files and identify duplicates
3. infer rename/move candidates
4. report unknowns and wait for David's approval
5. execute only the approved plan
6. preserve originals or archive them instead of deleting

See `docs/claude-cli-operating-pattern.md`.

## Wiki Layer

The Karpathy-style Obsidian wiki layer is installed locally as `olw 0.8.3` and
has a test workspace at `D:\FAP\wiki-compiler`.

See `docs/karpathy-wiki-layer.md`.

## First Use

Create a new workflow packet:

```bat
scripts\create_workflow_packet.bat PaperGrading
```

Then drop files into:

```text
workflows/PaperGrading/INPUT/
```

Run:

```bat
workflows\PaperGrading\RUN_PIPELINE.bat
```
