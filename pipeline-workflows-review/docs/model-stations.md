# Model Stations

These are proposed verification stations for the FAP/Theophysics production
pipeline. Model weights and caches do not belong in this repo. This repo only
stores station contracts, scripts, prompts, and setup notes.

## Claim Extraction

Purpose: break papers into discrete factual claims.

Suggested tooling:

- FactDetect-style scientific claim decomposition
- Ollama/Mistral prompt fallback for local extraction

Output: claim rows for fact, contradiction, timeline, and math stations.

## Fact Verification

Purpose: classify claims as supported, refuted, or insufficiently evidenced.

Suggested local pieces:

- SBERT embeddings
- Qdrant retrieval
- DeBERTa/RoBERTa NLI
- domain source library

This is retrieval plus comparison, not just a single model call.

## Contradiction Detection

Purpose: compare statement pairs and flag contradiction, entailment, or neutral.

The large use case is the Bible-contradiction lane: generic NLI can detect
semantic conflict, while a Theophysics-specific dataset can teach the difference
between a real contradiction and complementary accounts.

## Timeline Verification

Purpose: extract dates/events, build temporal sequences, and check ordering.

Suggested source of truth:

- existing Postgres Bible warehouse timeline tables
- known periods, events, and verse-event links

Output should flag mismatches, missing anchors, and ordering violations.

## Math Verification

Purpose: parse equations, numeric claims, variables, and RHS/LHS agreement.

Suggested tooling:

- symbolic math where possible
- arithmetic validation
- equation extraction
- tolerance thresholds for rounded values

This station catches number contradictions and malformed quantitative claims.

## Paper Review

Purpose: synthesize the station results into a human-readable judgment.

Suggested tooling:

- Ollama/Mistral or stronger LLM
- custom paper grading prompt
- rubric Excel as source data

This station should not invent evidence. It reads station outputs.
