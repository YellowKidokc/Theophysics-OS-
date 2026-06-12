# MYTHOS INTEGRATION PROMPT — Wire Orchestrator to Pipeline Engine
## POF 2828 | June 10, 2026

## TOKEN CONSTRAINT
This task should complete in under 15,000 tokens of output. The architecture
decisions are already made. You are wiring, not designing. If you find yourself
writing more than 15K tokens, you are overbuilding.

## THE JOB

Two systems exist in this repo that do overlapping things. Connect them.

### System A: Pipeline Engine (engines/pipeline/)
- `pipeline_engine.py` — 444 lines. File watcher (watchdog), Postgres logging,
  signal routing, manifest tracking, station chaining. Has `register_station()`,
  `sweep()`, `start()/stop()`, `get_status()`.
- `station_base.py` — 157 lines. `StationBase` ABC, `StationVerdict` enum,
  `Signal`/`Manifest` dataclasses. THE shared interface.
- `station_runner.py` — 60 lines. Preference-aware runner with JSONL logging.
- `stations/` — 11 Python station implementations (axiom_mapper, classifier,
  paper_grader, vectorizer, etc.)

### System B: Orchestrator (scripts/)
- `orchestrator.py` — 401 lines. DAG runner. Reads workflow JSON, resolves
  `depends_on`, runs stages concurrently, writes STATUS.json and MANIFEST.json,
  handles `on_error` (stop/skip/continue), supports LLM gates and dry-run mode.
- `external_adapter.py` — Wraps X:\Backside RUN.bat stations into `StationBase`.
- `correction_logger.py` — Structured training data capture.

### The Problem
The orchestrator creates `DryRunStation` instances for every station because it
doesn't know about the 11 Python station implementations in `engines/pipeline/stations/`.
The pipeline engine doesn't know about DAG workflow definitions or STATUS tracking.
They share `StationBase` but don't talk to each other.

## WHAT TO DO

1. **Create `engines/pipeline/station_factory.py`** — A factory that resolves a
   station name to the correct implementation:
   - If the station has a Python implementation in `engines/pipeline/stations/`,
     instantiate that class.
   - If the station is in STATION_REGISTRY.json with a path to X:\Backside,
     instantiate `ExternalStationAdapter`.
   - If neither exists and `dry_run=True`, instantiate `DryRunStation`.
   - If neither exists and `dry_run=False`, raise an error.

2. **Update `orchestrator.py`** — Replace the inline `DryRunStation` fallback with
   a call to `station_factory.resolve(station_name)`. The orchestrator should not
   know about specific station classes — it asks the factory.

3. **Add Postgres logging to orchestrator** — When the pipeline engine is available,
   the orchestrator should log actions to Postgres via `pipeline_engine._log_to_pg()`.
   Make this optional — if Postgres is unreachable, fall back to local JSONL (which
   it already does via STATUS.json).

4. **Update `engines/pipeline/__init__.py`** — Export `station_factory`, `ExternalStationAdapter`.

5. **Do NOT delete or rewrite** `pipeline_engine.py`, `orchestrator.py`, or any
   existing station implementations. Wire them together. Both systems stay.

## CRITICAL RULES
- Do not exceed 15,000 tokens of output
- Do not rewrite existing files from scratch — surgical edits only
- Do not add new dependencies
- The `StationBase` interface is the contract — everything goes through it
- Test: `python -m pytest tests/ -x` must still pass after changes
- Vectorize BEFORE classify — do not reorder any workflow stages