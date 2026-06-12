# CODEX BUILD PROMPT — FORGE Pipeline Integration
## POF 2828 | June 10, 2026
## What exists, what was just added, and what you need to build

---

## SITUATION

The pipeline-workflows repo at https://github.com/YellowKidokc/pipeline-workflows
already has a working Python pipeline engine. Claude (Opus) just added registry files,
schemas, DAG workflow definitions, a bridge adapter, and a correction logger.

Your job: wire everything together so the engine can run both its internal Python
stations AND the 47 external stations on X:\Backside through the same interface.

---

## WHAT ALREADY EXISTS (DO NOT REWRITE)

### Engine Core (engines/pipeline/)
- `pipeline_engine.py` — 444 lines. File watcher (watchdog), Postgres logging,
  signal routing, manifest tracking, station chaining. KEEP THIS.
- `station_base.py` — 157 lines. StationBase ABC, StationVerdict enum, Signal,
  Manifest dataclasses. KEEP THIS.
- `station_runner.py` — 60 lines. Preference-aware runner with JSONL logging. KEEP THIS.
- `stations/` — 11 Python station implementations (axiom_mapper, classifier, paper_grader,
  vectorizer, etc.). KEEP THESE — they are the internal stations.

### Workflow Packets (workflows/)
- 10 concrete workflow folders: BrainHandoff, ClipSyncExport, CorpusTriage, CrawlIngest,
  PaperGrading, SubstackPublish, TikTokPrep, TTSRender, VaultCompiler, VaultPageCompiler
- Each follows the folder contract (INPUT/OUTPUT/REVIEW/ARCHIVE/ERROR/CONFIG/PREFS/PROMPTS/SCRIPTS/LOGS)
- KEEP THESE — they are the packet-based workflows.

### Other Existing Code
- `scripts/` — create_workflow_packet, resolve_preferences, run_paper_mill, export_rubric, etc.
- `prompts/fap/` — 8 LLM prompt templates
- `preferences/` — defaults.json, profiles (brain, clipsync, paper_grading, tts_render)
- `tests/` — 14 test files
- `docs/` — architecture, station-contract, preference-layer, routing-contract, etc.

---

## WHAT CLAUDE JUST ADDED (REVIEW AND INTEGRATE)

### Schemas (schemas/)
- `station.schema.json` — station I/O contract with canary tracking
- `workflow.schema.json` — DAG workflow definition
- `status.schema.json` — packet state tracking
- `manifest.schema.json` — all packets in flight
- `model.schema.json` — model slot config
- `correction.schema.json` — human correction events (THE TRAINING DATA)
- `signal.schema.json` — already existed, was not modified

### Registries
- `stations/STATION_REGISTRY.json` — all 47 X:\Backside stations with paths, canary results,
  categories (analysis, framework, processing, media, graph, intelligence)
- `models/MODEL_REGISTRY.json` — all 19 model slots with preference chain order and BIL signal weights
- `workflows/WORKFLOW_REGISTRY.json` — 9 DAG workflows indexed by phase

### DAG Workflow Definitions (workflows/*.json)
- `sandbox-file-intake.json` — Phase 0 safety loop (RUN THIS FIRST)
- `paper-analysis.json` — full NLP stack
- `mda-publication.json` — MDA series pipeline
- `gtq-publication.json` — Genesis to Quantum pipeline
- `content-ingest.json` — new content intake
- `media-pipeline.json` — YouTube/audio pipeline
- `knowledge-graph.json` — claim -> vector -> graph -> Postgres
- `preference-learning.json` — continuous preference feedback
- `idle-processor.json` — scheduled batch processing

### Bridge Adapter (engines/pipeline/external_adapter.py)
- `ExternalStationAdapter` — wraps X:\Backside RUN.bat stations into StationBase interface
- `from_registry()` — builds adapter from STATION_REGISTRY.json entry
- Handles: file copy to INPUT, RUN.bat execution, output checking, idempotency, exit code conventions

### Correction Logger (scripts/correction_logger.py)
- Captures human corrections as structured JSONL
- Pushes to BIL server at localhost:8420
- Feeds preference learning workflow

### Config
- `pipeline.config.json` — all paths, ports, connection strings (placeholders for secrets)
- `.gitignore` — updated with .wrangler/, .claude/, STATUS.json, MANIFEST.json, model weights

---

## WHAT YOU NEED TO BUILD

### Phase 1: Validate and Fix Claude's Additions
1. Verify `stations/STATION_REGISTRY.json` is valid JSON (it was built by appending — may need fixing)
2. Verify all schema files validate against JSON Schema draft 2020-12
3. Verify `external_adapter.py` imports resolve correctly within the engines package
4. Add `external_adapter` to `engines/pipeline/__init__.py`
5. Run `python -c "from engines.pipeline.external_adapter import ExternalStationAdapter"` to confirm

### Phase 2: Orchestrator (scripts/orchestrator.py)
Build the DAG runner that reads workflow JSON files and executes them:
- Load workflow .json from workflows/
- Read STATUS.json if resuming — skip completed stages
- Resolve depends_on before running each stage
- For each stage: look up station in STATION_REGISTRY, instantiate ExternalStationAdapter or internal station
- Support parallel stages (multiple stations concurrently)
- Run LLM gates via Ollama (phi4) when configured
- Check idempotency via input hash before processing
- Write STATUS.json after each stage
- Update MANIFEST.json
- Respect on_error (stop|skip|continue)
- Log to LOGS/ in packet folder

### Phase 3: Setup Script (scripts/setup.py)
- Validate all paths from pipeline.config.json exist
- Check Python deps (watchdog, psycopg2, requests)
- Check Ollama available at configured endpoint
- Ping BIL server at port 8420
- Write validated config

### Phase 4: Station Config Files
Create individual .json configs for each station category. Use station.schema.json as the contract.
Organize under:
- `stations/analysis/` — 7q-classifier, claim-extractor, deberta-runner, sbert-embedder, etc.
- `stations/framework/` — fruits-spirit-canon, master-equation-canon, trinity-canon, etc.
- `stations/processing/` — readability-rewriter, conversion-station, image-processor, etc.
- `stations/media/` — whisper-transcribe, youtube-fetch, youtube-qa, etc.
- `stations/graph/` — graph-linker, postgres-sync, graphify, etc.
- `stations/intelligence/` — file-intelligence, preference-engine, classify-documents, etc.

Each config needs: name, path, type, status, input{accepts, source}, output{produces, destination},
llm_checkpoint, dependencies, idempotency, canary status from STATION_REGISTRY.

### Phase 5: Sandbox Test
Create `templates/sandbox_test/` with the full folder contract.
Write a test script that:
1. Copies 5 sample files into sandbox INPUT/
2. Runs sandbox-file-intake workflow via orchestrator
3. Verifies: STATUS.json written, MANIFEST.json updated, originals untouched
4. Reports pass/fail

### Phase 6: Update Tests
Add tests for:
- `test_external_adapter.py` — ExternalStationAdapter from_registry, process mock
- `test_orchestrator.py` — DAG resolution, stage execution, error handling
- `test_correction_logger.py` — log_correction, get_corrections, get_stats
- `test_schemas.py` — validate all .json files against their schemas

### Phase 7: Update Docs
- `docs/ARCHITECTURE.md` — rewrite to reflect three-layer system (FIS/BIL/Pipeline)
- `docs/STATION_DOCTRINE.md` — vectorize BEFORE classify, three-AI convergence confirmed
- `docs/PREFERENCE_ENGINE.md` — River -> PPK -> Implicit chain, BIL signal weights
- `docs/PHASED_ROLLOUT.md` — Phase 0 sandbox first, success conditions per phase

---

## CRITICAL RULES

1. **Vectorize BEFORE classify** — doctrine, three-AI convergence confirmed
2. **No model weights in repo** — configs only, weights on NAS
3. **No secrets** — placeholders for tokens, IPs, passwords
4. **Stations are self-contained** — repo has configs pointing to X:\Backside
5. **STATUS.json in every packet** — no processing without state tracking
6. **Idempotency via input hash** — re-running must not double-process
7. **Preference layer observes, never blocks** — BIL calibrates, doesn't gate
8. **Ollama phi4 for LLM checkpoints** — not Claude, not GPT
9. **Nothing original is destroyed** — copies only, originals untouched
10. **FIS says what it is. BIL says how much it matters. Pipeline says what happens next.**
11. **DO NOT rewrite existing engine code** — extend it, wire into it, don't replace it
12. **DO NOT modify TTS Engine code**