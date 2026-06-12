# FAP System Overview
*Auto-maintained by the pipeline engine. Last updated: {{timestamp}}*

## What This Is

Folder Automations & Pipelines (FAP) is the nervous system of the Theophysics operation. It watches folders, processes files through stations, logs everything to Postgres, and talks back when it finds gaps, duplicates, or quality issues.

## Architecture Layers

```
┌─────────────────────────────────────────────────┐
│                  GUI Dashboard                   │
│         fap_dashboard.html (command center)       │
├─────────────────────────────────────────────────┤
│                  Wiki Layer                       │
│    Self-documenting operating manual (Obsidian)   │
│    Each station writes its own page               │
├─────────────────────────────────────────────────┤
│               LLM Hub Layer                       │
│    AI checkpoints — thinking stations             │
│    Ollama local / Claude API / queue-based         │
├─────────────────────────────────────────────────┤
│              Pipeline Engine                      │
│    Watchdog watchers + scheduled sweeps            │
│    Station registry + manifest tracking            │
│    Signal routing (reciprocal feedback)            │
├─────────────────────────────────────────────────┤
│              Media Transform Layer                │
│    Format detection + branch routing              │
│    text→TTS, script→video, audio→transcript       │
├─────────────────────────────────────────────────┤
│              Storage Layer                        │
│    Postgres (truth) + Vector DB (relationships)   │
│    Batch sync 2x/day, not real-time               │
├─────────────────────────────────────────────────┤
│              File System                          │
│    D:\FAP\ hot folders (gold icons)               │
│    NAS archive, R2 publish, Vault ingest          │
└─────────────────────────────────────────────────┘
```

## The Three Rules

1. **Wiki explains** — what the system is supposed to do, what it actually did, how things relate
2. **Postgres records** — source of truth for manifests, actions, signals, scores
3. **Pipeline operates** — moves files, fires processors, routes verdicts

Never let these overlap. The wiki doesn't store data. Postgres doesn't explain itself. The pipeline doesn't document itself except by updating wiki pages.

## Station Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| **Intake** | File enters, gets identified | Classifier, Deduplicator, Format Detector, STT Cleaner |
| **Transform** | Content modified or converted | Lossless Prep, Vectorizer, HTML Builder, TTS Render, Thumbnail |
| **Media Branch** | Routes by output medium | Text→paper pipeline, Script→TTS, Lecture→video, Audio→transcript |
| **Validate** | Quality gates with kick-back | Paper Grader, Voice Auditor, Axiom Mapper, Cross-Domain Check |
| **Route** | Final destination | Vault Drop, R2 Publish, Substack Queue, PG Warehouse, NAS Archive |
| **LLM Hub** | AI-powered thinking stations | Classification AI, Grading AI, Gap Detection AI, Summary AI |

## LLM Hub Stations

These are NOT real-time. They queue work and process in batches.

**Scheduling rules:**
- Watcher detects file → queues it for LLM processing
- LLM hub runs on schedule (every 15 min) or when queue > N items
- Heavy models (Claude API) run 2x/day batch
- Light models (Ollama local) can run more frequently
- Every LLM call logged with prompt, response, cost, latency

## Media Transformation

The classifier determines WHAT the content is. The media router determines what FORM it should take.

```
Content arrives → Classify (what is it?) → Media Route (what form?)
                                            ├── Text track: lossless → grade → publish
                                            ├── Audio track: TTS → audio QA → R2
                                            ├── Video track: script → render → upload
                                            └── Data track: normalize → warehouse → viz
```

## Postgres Sync

NOT real-time. Postgres is the ledger, not the nervous system.

- **Hot actions** (file moves, verdicts): logged to local JSONL immediately
- **Batch sync**: 2x/day, JSONL → Postgres bulk insert
- **Manifest snapshots**: every file's current state synced at batch time
- **Signal alerts**: these DO go to PG immediately (they're rare and important)

## File Structure

```
D:\FAP\
├── intake\           ← HOT FOLDER (gold icon)
├── classified\
├── lossless\
├── vectorized\
├── graded\
├── axiom-mapped\
├── output\
├── media\
│   ├── tts-queue\    ← HOT FOLDER
│   ├── tts-done\
│   ├── video-queue\
│   └── transcripts\
├── _review\          ← gray zone, needs David
│   ├── classifier\
│   ├── lossless\
│   ├── grader\
│   └── axiom-mapper\
├── _rejected\
├── _queue\           ← LLM hub work queue
│   ├── pending\
│   ├── processing\
│   └── completed\
├── wiki\             ← self-documenting pages
│   ├── system\
│   ├── stations\
│   ├── prompts\
│   └── logs\
└── logs\             ← local JSONL before PG sync
```

## Links

- [[Pipeline Stations]] — full station registry
- [[Document States]] — lifecycle of a document
- [[LLM Hub]] — AI checkpoint configuration
- [[Media Routes]] — transformation branch logic
- [[Prompt Library]] — all prompts used by LLM stations
- [[Error Recovery]] — what to do when things break
