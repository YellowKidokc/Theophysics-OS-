# NLP Output Contract

Every NLP pass should return a small, reliable record. It should not try to do everything at once.

The goal is to answer:

```text
What is this?
What is it about?
What should we call it?
Where might it go?
How sure are we?
```

## File-Level Output

For each file:

```json
{
  "filepath": "",
  "filename": "",
  "baseline": "lowercase-hyphen-name.ext",
  "summary": "One short sentence describing the file.",
  "classification": {
    "domain": "THEOPHYSICS",
    "domain_code": "TP",
    "subject": "coherence",
    "confidence": 72,
    "source": "filename|content|markov|nlp|cluster"
  },
  "keywords": ["coherence", "entropy", "master-equation"],
  "slug": "coherence-entropy-master-equation",
  "tags": ["draft", "research", "markdown"],
  "route": {
    "mode": "rename|manual|intelligence",
    "suggested_folder": "",
    "keep_in_place": true
  },
  "review": {
    "needs_review": true,
    "reason": "confidence below threshold"
  }
}
```

## Folder-Level Output

For each folder:

```json
{
  "folder_path": "",
  "folder_name": "",
  "summary": "One short sentence describing what is in this folder.",
  "dominant_domains": [
    {"domain": "DEVELOPMENT", "count": 14},
    {"domain": "DOCUMENTS", "count": 4}
  ],
  "keywords": ["api", "sorter", "sqlite", "rename"],
  "slug": "api-sorter-sqlite-rename",
  "file_count": 18,
  "folder_count": 3,
  "route": {
    "suggested_folder": "",
    "move_as_unit": true,
    "split_recommended": false
  },
  "review": {
    "needs_review": true,
    "reason": "mixed domains"
  }
}
```

## The Minimum Useful Return

If an NLP engine can only return four things, return these:

1. `summary`
2. `classification`
3. `keywords`
4. `slug`

The baseline name should always be computed before NLP:

```text
Original: Clipboard Text (2).txt
Baseline: clipboard-text-2.txt
```

NLP then improves the richer fields:

- better summary
- better domain
- better subject
- better keywords
- better slug
- better route

## Four Operations

The app can think in four verbs:

### A. Separates Things

Manual sorting, extension grouping, duplicate handling, flattening, and splitting mixed folders.

### B. Combines Things

Clustering, session grouping, folder-as-unit handling, and collecting related files.

### C. Names Things

Baseline cleanup, slug generation, naming presets, and schema-specific names.

### D. Routes Things

Suggesting destination folders, keep-in-place decisions, archive decisions, and Brain Hub/job-card export.

## Confidence Rules

High confidence:

- show as batch-approvable
- no NLP required unless user requests it

Medium confidence:

- show with reason and keywords
- allow quick approve/override

Low confidence:

- route to NLP
- ask for review
- do not auto-move or auto-rename

## SQLite Fields To Store

SQLite should store these normalized fields:

- baseline
- summary
- domain
- domain_code
- subject
- confidence
- source
- keywords_json
- slug
- tags_json
- suggested_folder
- keep_in_place
- needs_review
- review_reason

This keeps all pages aligned: manual sort, intelligence sort, and rename all speak the same language.
