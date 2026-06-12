# FORGE Pipeline Architecture

The current FORGE system is a three-layer routing stack:

```text
FIS says what it is.  BIL says how much it matters.  Pipeline says what happens next.
```

## 1. FIS: File Intelligence System

FIS identifies the object entering the system. Its job is classification metadata,
not routing authority:

- file type and normalized representation;
- domain, subject, slug, and confidence;
- candidate packet/workflow fit;
- signals for duplicates, gaps, quality issues, and readiness.

FIS stations may be internal Python stations or external `X:\Backside` stations.
External station code remains self-contained; this repo stores only registry and
contract metadata.

## 2. BIL: Behavioral Intelligence Layer

BIL observes preference and correction signals. It does not block the pipeline.
The preference layer calibrates priority, relevance, and future defaults by
using structured events such as human corrections, explicit ratings, opens,
exports, and reroutes.

The correction log is training data. Every human override is captured as JSONL
and can be pushed to the BIL server on port `8420` when available.

## 3. Pipeline: Workflow Orchestration

The pipeline layer decides what happens next by executing workflow DAGs from
`workflows/*.json`. Each packet uses the folder contract:

```text
INPUT/ OUTPUT/ REVIEW/ ARCHIVE/ ERROR/ CONFIG/ PREFS/ PROMPTS/ SCRIPTS/ LOGS/
```

The orchestrator reads a workflow, resolves `depends_on`, executes ready stages,
runs explicitly parallel station groups concurrently, records every stage in
`STATUS.json`, and updates `MANIFEST.json` for global packet visibility.

## Station Execution Model

- Internal Python stations continue to use `StationBase`.
- External `X:\Backside` stations are wrapped by `ExternalStationAdapter`.
- Registries (`stations/STATION_REGISTRY.json`, `models/MODEL_REGISTRY.json`,
  `workflows/WORKFLOW_REGISTRY.json`) are the source of truth.
- Station category configs in `stations/<category>/<station>.json` document I/O,
  idempotency, LLM checkpoint policy, and canary status.

## Safety Doctrine

1. Phase 0 sandbox runs first.
2. Originals are copied, never moved or destroyed.
3. Every packet has `STATUS.json` before meaningful processing.
4. Idempotency is by input hash.
5. Vectorize before classify.
6. LLM gates use local Ollama `phi4`.
7. No secrets or model weights are committed.
