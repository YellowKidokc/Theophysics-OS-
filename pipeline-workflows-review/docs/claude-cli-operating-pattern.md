# Claude CLI Operating Pattern

This is the repeatable pattern for local Claude CLI sessions that can see the
filesystem.

## Core Rule

Inventory first. Propose second. Execute only after David approves.

This keeps local cleanup powerful without letting a model silently rearrange a
vault, repo, or workflow folder.

## Phase 1: Inventory

Claude CLI should:

- list all source folders in scope
- count files by extension
- compute SHA256 hashes for duplicate detection
- detect byte-identical files
- detect near-duplicates when useful
- identify pre-existing rename maps or local instructions
- identify files that belong outside the current project
- report all unknowns

No file moves happen in Phase 1.

## Phase 2: Approval Packet

Claude CLI should return a clean decision packet:

- confirmed duplicates
- proposed archive/move/rename plan
- files that need David's call
- recommended split between tactical/deploy material and deep research material
- exact target folders
- whether originals are preserved, archived, or left in place

The output should be specific enough that David can answer with short calls.

## Phase 3: Execute

After approval, Claude CLI should:

- create target folders
- move or copy files exactly as approved
- archive duplicates instead of deleting by default
- honor existing rename maps
- write a change log
- write a final summary with counts

## Approval Example

```text
Approved. Here are my calls:

new 1.txt -> _FLAG_BELONGS_ELSEWHERE/. I will relocate it later.
Untitled 10 vs 6 -> keep both as v1/v2. Rename per your suggestions.
Go hybrid. Move topical deep-research docs to matching numbered folders.
Keep TikTok lean as the tactical deploy kit.
Archive duplicate Pew/Religion files per your counts.
Rename Scientific method Untitleds per the existing _FILE_RENAME_MAP.
Rename Propaganda.txt -> BERNAYS_DISSECTION.md.
Proceed to Phase 2: write the full file-by-file move plan.
```

## Why This Belongs In The Pipeline

This is a human-in-the-loop station behavior. The model can do deep local
analysis, hashing, clustering, and move planning, but David keeps authority over
the final reorganizing act.
