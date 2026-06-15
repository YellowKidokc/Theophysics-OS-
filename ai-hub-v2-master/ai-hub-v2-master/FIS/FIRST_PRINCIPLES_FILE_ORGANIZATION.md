# First Principles: File Organization

The File Sorter Hub should not start with buttons. It should start with the reason a person is touching a pile of files.

Every file operation is one of these jobs:

1. Find it later.
2. Understand what it is.
3. Decide what to keep.
4. Put related things together.
5. Preserve context.
6. Prepare it for another system.
7. Reduce clutter safely.

From those jobs, the app needs a few different sorting modes instead of one universal sorter.

## 1. Manual Cleaning

User intent: I know roughly what I want. Help me do it faster and safely.

This is not AI-first. It is control-first.

Examples:

- isolate extensions
- gather images, PDFs, archives, videos, code, documents
- flatten a folder
- keep folder structure
- view folders as groups
- view all files flat
- find duplicate names
- find duplicate hashes
- choose which duplicate survives
- delete or move only after review

Core rule: never destroy context without a preview.

The page should support:

- scan folder
- filter by extension/type
- grouped view by folder
- flat view
- duplicate groups
- keep biggest/smallest/newest/oldest/first
- dry-run operations
- output folder selection

This is the file cleaner page.

## 2. Intelligence Sorting

User intent: I do not know what all this is. Show me what the machine thinks.

This is classification-first.

The system reads file names, paths, extensions, timestamps, and content where safe. Then it predicts:

- domain
- subject
- keywords
- confidence
- source of prediction
- suggested folder
- suggested name

The intelligence path should have tiers:

1. Fast filename/path/extension scan.
2. Content keyword extraction.
3. Markov/preference prediction from prior decisions.
4. Optional NLP/model read for low-confidence files.
5. Optional cluster discovery when there is no good domain map.

Core rule: confidence decides how much machine effort is worth spending.

High confidence can be approved in batches. Low confidence should be routed to deeper analysis or manual review.

## 3. Rename System

User intent: Keep files where they are, but make names meaningful.

Renaming is different from sorting. It changes the address label, not the location.

There should always be a baseline:

```text
lowercase-words-with-hyphens.ext
```

Then richer schemas can be layered on top:

```text
{domain}_{slug}_{seq}.{ext}
{date}_{slug}_{domain}.{ext}
{domain}.{seq} {slug}.{ext}
PRIMARYVAR__ENTITY__STATE__DATE__SHORTCODE.ext
```

The important design move is component prediction:

- domain
- slug
- sequence
- state
- subject
- date
- shortcode

Each component can be accepted or corrected separately. That lets the learning system improve faster than if it only learned whole filenames.

## 4. Folder-as-Unit Sorting

User intent: Do not pull this folder apart. Classify the whole folder.

Sometimes the folder is the unit, not the file.

The system should inspect a folder by:

- folder name
- top file names
- dominant extensions
- recent timestamps
- repeated keywords
- child folder names
- representative file content

Then it can propose:

- keep folder here
- move whole folder to a domain
- rename folder
- split folder only if the internal clusters are clearly different

Core rule: preserve folder context unless the user chooses to break it.

## 5. Cluster Discovery

User intent: I do not know the categories yet. Let the data show me.

This is not supervised domain sorting. It is discovery.

Feature matrix:

- filename tokens
- content keywords
- extension
- path context
- modified/created time
- file size
- neighboring files
- prior decisions

The system groups natural clusters and names them from their strongest signals.

Examples:

- a work session from a 3-hour timestamp window
- all files mentioning a project/entity
- all screenshots from a UI build
- all PDFs and notes around one research search

Core rule: clusters are proposals, not truth.

## 6. Storage And Memory

SQLite is the app memory.

It should remember:

- files seen
- scan runs
- classifications
- name predictions
- folder predictions
- duplicate groups
- user decisions
- operations performed
- operation undo metadata where possible

The GUI should pull from SQLite first, then scan in the background.

This makes the app feel alive instead of empty every time it opens.

## 7. Root Contexts

Before sorting individual files, the system should know which root it is inside.

A drive, share, or mapped folder is a context boundary:

- Obsidian knowledge
- transfer inbox
- Theophysics
- GitHub repos
- Brain system
- AI workspace
- photos
- videos
- Docker
- backups
- downloads

The same filename can mean different things in different roots.

Example:

```text
X:\08_DASHBOARDS\FILE SORTER
```

This is not just a path. It is inside the Brain System root, under dashboards, inside a file organization tool. That context should influence classification and naming.

Good root names should carry:

- order number
- short code
- human name
- role

Example:

```text
06-BRN_Brain_System
02-TP_Theophysics
01-XFER_Transfer_Inbox
04-GH_GitHub_Repos
```

Core rule: the root tells the sorter what kind of world it is standing in.

## 8. Safe Operation Ladder

Every action should climb this ladder:

1. Observe.
2. Cache.
3. Predict.
4. Preview.
5. Select.
6. Apply.
7. Log.
8. Learn.
9. Undo or recover where possible.

Nothing destructive should skip the preview step.

## 9. The Three Main Pages

### Home

Question: what do you want to do?

- sort files myself
- let intelligence sort
- rename files

Home also shows SQLite memory:

- last scan
- cached files
- pending decisions
- recent operations

### Manual Sort

For extension sorting, flattening, duplicate review, grouping, and cleanup.

### Intelligence Sort

For classification, confidence review, NLP routing, clustering, and learned decisions.

### Rename

For baseline cleanup, naming presets, component prediction, and schema-specific renaming.

## 10. What To Avoid

- one giant page with every control
- moving files before showing a dry run
- treating folders and files as the same thing
- forcing every user into one naming system
- requiring heavy models before the basic app works
- rescanning from scratch every time the GUI opens

## 11. Product Shape

The product is not "an AI sorter."

It is a local file operating system for:

- cleaning
- classifying
- naming
- remembering
- learning
- safely applying changes

The first product promise should be:

```text
See what you have, decide what matters, and make the next move safely.
```
