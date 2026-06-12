# Phased Rollout

## Phase 0: Sandbox First

Workflow: `sandbox-file-intake`

Success conditions:

- test packet has the full folder contract;
- five copied sample files process through the DAG;
- `STATUS.json` is written;
- `MANIFEST.json` is updated;
- originals remain byte-for-byte untouched;
- no external production folder is required for dry-run safety validation.

## Phase 1: Core Intake and Analysis

Workflows: `content-ingest`, `paper-analysis`, `knowledge-graph`

Success conditions:

- intake normalizes documents;
- vectorization runs before classification;
- classification, claims, graph, and sync stages record status;
- error policy (`stop`, `skip`, `continue`) behaves per workflow definition.

## Phase 2: Publication and Media

Workflows: `mda-publication`, `gtq-publication`, `media-pipeline`

Success conditions:

- media and article packets preserve originals;
- publication routes are recorded in packet status;
- Postgres/vault/R2 targets remain configuration only unless runtime secrets are
  supplied externally.

## Phase 3: Continuous Learning and Idle Processing

Workflows: `preference-learning`, `idle-processor`

Success conditions:

- BIL correction events accumulate locally if the service is offline;
- River -> PPK -> Implicit preference chain receives replayable data;
- idle batches obey configured limits and do not block active packet work.
