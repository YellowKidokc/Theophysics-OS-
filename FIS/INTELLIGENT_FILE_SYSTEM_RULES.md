# Intelligent File System Rules

These rules came from the working clipboard notes and are now the local source of truth for the first clustering pass.

## Core Loop

Normalize -> Compare -> Cluster -> Decide -> Preview -> Approve -> Act -> Record

## Name Memory

- `original_name`: never changed record
- `normalized_name`: machine-clean version for comparison
- `approved_name`: final human-approved name, if one exists

Do not lose the original spelling. Normalize for comparison only.

## Normalization V1

1. Lowercase names.
2. Trim leading and trailing spaces.
3. Replace spaces and underscores with hyphens.
4. Remove repeated hyphens.
5. Remove punctuation that does not help meaning.
6. Preserve meaningful numbers, dates, versions, and file extensions.
7. Use aliases and spelling corrections for suggestions, not silent file changes.

## Alias Seeds

```yaml
aliases:
  autohotkey:
    - ahk
    - auto hot key
    - auto-hot-key
    - auto hotkey
    - auto-hotkey
    - autohotkey

  programming:
    - progaimng
    - programing
    - programming

  attachment:
    - attache
    - attach
    - attachment
    - attachments
```

## Cluster Decisions

Use five decision types first:

- `combine`
- `separate`
- `create_hub`
- `deduplicate`
- `archive`

Default rule: do not merge automatically.

- Same theme, different roles: `create_hub`
- Same theme, same role: recommend `combine`
- Same file repeated: recommend `deduplicate`
- Archive/export/temp/system residue: recommend `archive`
- Low confidence: recommend `review`

## First Test Clusters

- AutoHotkey: `AutoHotKeyGreat`, `AutoHotkey`, `Auto Hotkey`, `Auto Hot Key`, `AHK`
- Books/PDF/EPUB: Anthony Robbins, ebooks, Notion PDFs
- Trading/Investing: daily market, investing, pattern search
- Emotions/Affirmations: emotions, affirmations
- Export/Archive/Junk: exports, archives, attachments, `.trash`, `_gsdata_`, changed files

## Safety

The system can auto-create scan records, cluster previews, rename previews, hub suggestions, sidecar metadata, and SQLite cache records.

It must require approval before rename, move, combine, delete, archive, or deduplicate actions.
