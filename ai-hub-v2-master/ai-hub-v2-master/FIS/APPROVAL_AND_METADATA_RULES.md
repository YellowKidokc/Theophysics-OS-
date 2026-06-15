# Approval and Metadata Rules

## Storage Split

```text
SQLite = full cache, evidence, history, and action journal
JSON = portable folder/file sidecar metadata
Markdown = human-readable reports
```

Folder sidecars use:

```text
.folderbrain.json
```

File sidecars can later use:

```text
filename.ext.brain.json
```

The sidecar stays compact. It should hold identity, state, counts, top extensions, classification summary, available actions, and last scan status. It should not hold every file record.

## Approval Loop

The GUI should show choices, not only approve/reject.

```text
Rules suggestion
NLP suggestion
Preference suggestion
Custom answer
```

Every corrected choice becomes training data.

Minimum approval fields:

```text
domain
tags
summary
rename preset
suggested action
cluster decision
```

## Preference Engine Role

River is the first planned live learner, but it should not be the semantic brain and it should never directly move, rename, delete, merge, or archive.

```text
NLP = understands content
Rules = make structure predictable
River = learns David's choices
SQLite = remembers decisions
JSON = carries metadata with folders/files
GUI = approval surface
```

Simple rule:

```text
Show 3 machine options + 1 custom option.
David chooses.
Preference engine learns.
Nothing destructive happens without approval.
```
