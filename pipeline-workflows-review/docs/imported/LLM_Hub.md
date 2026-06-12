# LLM Hub — AI Hierarchy
*Auto-maintained. Last updated: {{timestamp}}*

## The Chain of Command

```
File arrives at station
        │
        ▼
┌──────────────────┐
│   TIER 1: Ollama │  ← worker, runs every 15 min, FREE
│   (local, fast)  │
│                  │
│  confidence > 0.55 → PASS, move to next station
│  confidence < 0.55 → ESCALATE to Tier 2
└────────┬─────────┘
         │ escalation
         ▼
┌──────────────────┐
│  TIER 2: Claude  │  ← executive, runs 2x/day, COSTS MONEY
│  (API, powerful) │
│                  │
│  confidence > 0.40 → PASS with high-quality result
│  confidence < 0.40 → ESCALATE to Tier 3
└────────┬─────────┘
         │ escalation
         ▼
┌──────────────────┐
│  TIER 3: David   │  ← final authority, review queue
│  (human, costly) │
│                  │
│  Decision feeds back into threshold calibration
│  System LEARNS from David's choices
└──────────────────┘
```

## Backend Configs

### Ollama (Tier 1 — The Worker)
- **Model:** mistral (swap for whatever's loaded)
- **Schedule:** Every 15 minutes
- **Cost:** $0.00
- **Max input:** 4,000 chars (truncated for speed)
- **Escalation threshold:** 0.55
- **Tasks:**
  - `classify_document` — what is this file?
  - `stt_cleanup` — remove speech-to-text artifacts
  - `format_detect` — what format is this?
  - `keyword_extract` — pull topic keywords
  - `quick_quality` — fast quality score
  - `dedup_check` — is this a duplicate?

### Claude API (Tier 2 — The Executive)
- **Model:** claude-sonnet-4-20250514
- **Schedule:** 2x/day batch (or on escalation)
- **Cost:** ~$0.003/1k tokens
- **Max input:** 16,000 chars
- **Escalation threshold:** 0.40
- **Tasks:**
  - `grade_paper` — full quality assessment
  - `cross_domain_analysis` — is the physics↔theology bridge structural?
  - `axiom_mapping` — which axioms does this support?
  - `gap_detection` — what's missing from the framework?
  - `voice_audit` — does this sound like David?
  - `escalated_classification` — Ollama wasn't sure, Claude decides

### Local Embeddings (Tier 1 — The Librarian)
- **Model:** all-MiniLM-L6-v2
- **Schedule:** Every 15 minutes
- **Cost:** $0.00
- **Tasks:**
  - `vectorize` — generate embeddings for semantic search
  - `similarity_check` — find near-duplicates

## Escalation Rules

1. Escalation is AUTOMATIC — no human intervention needed
2. The escalating backend includes its partial result as context
3. Claude sees: "Ollama scored this 0.42, here's what it found, please verify"
4. David sees: "Claude scored this 0.35, here's the full analysis, please decide"
5. David's decisions are logged and used to recalibrate thresholds over time

## Cost Tracking

Every LLM call is logged to `D:\FAP\logs\llm_jobs.jsonl` with:
- Backend used
- Token count (input + output)
- Latency in ms
- Whether it was escalated
- Final verdict

Daily cost report generated at batch time.

## Prompt Library

All prompts live in `D:\FAP\wiki\prompts\` as markdown files.
Each prompt has `{{INPUT}}` placeholder for the document text.

Current prompts:
- [[classify_document]] — Tier 1 classification
- [[grade_paper]] — Tier 2 paper grading

## Links

- [[System Overview]] — full architecture
- [[Pipeline Stations]] — station registry
- [[Error Recovery]] — what happens when backends fail
