# Preference Layer

The preference layer is the shared memory of how David wants the system to act.
It does not replace station logic. It guides station logic.

## What Belongs Here

- model lanes: fast, strong, backup, local-only, cloud-allowed
- cleanup style: light spellcheck, STT repair, coherent rewrite
- output tone: terse, handoff-ready, publish-ready, TTS-friendly
- run behavior: dry run, stop for review, continue through route
- destination defaults: vault, R2, NAS, Substack queue, clipboard vault
- safety defaults: preserve originals, no secret export, no model weights

## What Does Not Belong Here

- private tokens
- full local model paths
- vector databases
- source document dumps
- station implementation code

## Resolution Order

When a workflow runs, preferences should resolve in this order:

1. `preferences/defaults.json`
2. `preferences/profiles/*.json`
3. `workflows/PROCESS_NAME/PREFS/preferences.json`
4. command-line override

Later layers can override earlier layers. If a station cannot honor a
preference, it should write a `QUALITY` or `UPSTREAM` signal instead of silently
doing the wrong thing.

## Why This Matters

The same pipeline can serve different fronts:

- Brain intake wants durable handoffs and retrieval-ready summaries.
- ClipSync wants portable HTML, relative assets, and daily exports.
- TTS render wants clean speech, restartable playback, and readable chunks.
- Paper grading wants evidence, score ledgers, and stop points.

Those should not be four separate systems. They should be one station graph with
different preferences.
