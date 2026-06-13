# Karpathy-Style Wiki Layer

This layer turns raw notes into a living Obsidian-style wiki.

The local implementation currently uses:

- `obsidian-llm-wiki`
- command: `olw`
- verified version: `0.8.3`
- local workspace: `D:\FAP\wiki-compiler`
- fast model: `qwen2.5:3b`
- heavy model: `phi4`
- Ollama URL: `http://localhost:11434`

## Local Workspace

```text
D:\FAP\wiki-compiler\
  raw\
  wiki\
  wiki\.drafts\
  wiki\sources\
  wiki.toml
  vault-schema.md
```

Confirmed test sources:

- `raw\entropy_adversary.md`
- `raw\grace_operator.md`

Confirmed draft outputs:

- `wiki\.drafts\Adversary (Eve).md`
- `wiki\.drafts\Cross as Grace Operator.md`
- `wiki\.drafts\Entropy.md`
- `wiki\.drafts\The Grace Operator.md`

## Role In The Pipeline

This is the final production-vault station.

```text
raw source
  -> classification
  -> lossless prep
  -> claim/fact/math/timeline checks
  -> Excel rubric
  -> HTML report
  -> Obsidian wiki compiler
  -> 7-layer production vault page
```

## Operating Principle

Raw files are preserved. Generated wiki pages are outputs.

The compiler should receive cleaned, lossless source material and rubric
metadata, then produce linked pages with:

- frontmatter
- summaries
- core article body
- technical layer
- wikilinks
- receipts
- framework impact

See `docs/vault-page-architecture.md`.

## Current Gap

The tool is installed and working, but it is not yet wired into the standardized
workflow packet runner. The next implementation step is to make
`workflows/VaultPageCompiler/RUN_PIPELINE.bat` call the wiki compiler against a
known input folder and write logs into the packet `LOGS` folder.
