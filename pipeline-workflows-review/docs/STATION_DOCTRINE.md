# Station Doctrine

## Prime Rule: Vectorize Before Classify

Vectorization must occur before classification in analysis workflows. This is a
confirmed three-AI convergence point: semantic structure should be generated
before a label is assigned, so downstream classifiers operate with context
instead of isolated text.

Canonical sequence:

```text
intake -> vectorize -> cluster/context -> classify -> extract/grade/route
```

## Station Boundaries

Stations are self-contained units with explicit I/O contracts. A station may be:

- an internal Python `StationBase` implementation under `engines/pipeline/`; or
- an external `X:\Backside` station with `RUN.bat` wrapped by the bridge adapter.

The pipeline orchestrates stations but does not rewrite their internals.

## Data Safety

- Input originals are copied into station `INPUT/` folders.
- No station should destructively modify source files.
- Re-runs must use input-hash idempotency to avoid double processing.
- Review and error outcomes must be visible in packet state.

## LLM Checkpoints

LLM checkpoints are gates, not the primary engine. When a workflow defines an
LLM gate, it uses local Ollama `phi4` by default. External SaaS models are not
required for gate decisions.
