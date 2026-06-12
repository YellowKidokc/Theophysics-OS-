# Claude CLI Prompt: Vault Folder Compile

You are working inside a local Theophysics vault folder. Your job is to inventory
and prepare a compile plan. Do not move, rename, delete, or rewrite source files
until David approves the plan.

## Phase 1: Inventory Only

1. List the folders in scope.
2. Count files by extension.
3. Compute SHA256 hashes for duplicate detection.
4. Identify byte-identical duplicates.
5. Identify likely near-duplicates or v1/v2 pairs.
6. Detect local rename maps or instruction files.
7. Flag files that appear to belong outside this project.
8. Report all unknowns.

## Phase 2: Ask For Decisions

Return a concise decision packet with:

- what you found
- what you recommend
- exact move/rename/archive plan
- any files that need David's decision

Wait for approval.

## Phase 3: Execute Approved Plan

Only after approval:

- create target folders
- move/copy/archive exactly as approved
- preserve originals unless David says otherwise
- write a final change log

## Output Target

Compiled production vault pages should follow:

`docs/vault-page-architecture.md`

The raw source is preserved. The compiled page is the new production output.
