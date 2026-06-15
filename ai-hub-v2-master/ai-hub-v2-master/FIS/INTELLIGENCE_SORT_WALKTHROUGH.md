# RIVER FIS — Intelligence Sort Walkthrough Spec
## For Codex: Build this into the "Let Intelligence Sort" simple mode flow
## POF 2828 | 2026-06-14

---

## What the scan finds (and why)

The intelligence sort reads finding cards from SQLite — things the cache scan
already detected. Each finding has a WEIGHT (1-10) that determines the order
it's shown and how urgent it is.

### The weight system explained to the user

```
WEIGHT 10 — PROTECTED (do not touch)
  System folders (.git, .venv, node_modules, __pycache__, _gsdata_)
  These exist for a reason. Moving or renaming them breaks things.
  → River says: "I found this. I will not touch it. No action needed."

WEIGHT 9 — PROJECT SEEDS (protect, do not archive)
  Small folders that contain README.md, .git, pyproject.toml,
  package.json, requirements.txt, config.json.
  These look small but they're real projects starting.
  → River says: "This looks like a project. I marked it protected."

WEIGHT 9 — EXACT DUPLICATES (same hash, same size)
  Two files with identical content in different locations.
  → River says: "These are the same file. Keep one, review the other."

WEIGHT 8 — BAD NAMES (rename candidates)
  ALL CAPS, spaces, special characters, "New Folder", "Untitled",
  "AAA priority hack", UUID/hash names, misspellings.
  → River says: "These names are messy. Here's what clean looks like."

WEIGHT 8 — WRONG LOCATION
  Files that don't belong where they are.
  Scripts in a photo folder. PDFs on the desktop. Logs mixed with papers.
  → River says: "This file might be in the wrong place."

WEIGHT 7 — ARCHIVE RESIDUE
  Old export folders, zip extracts left behind, dated backup copies.
  → River says: "This looks like leftover export material."

WEIGHT 7 — MISSING METADATA
  Folders without .folderbrain.json — the system doesn't know them yet.
  → River says: "I haven't mapped this folder. Want me to create a card?"

WEIGHT 7 — UNKNOWN FILES
  Files the system can't classify by extension or content.
  → River says: "I don't know what this is. You should review it."

WEIGHT 6 — SIMILAR FOLDER NAMES
  "AutoHotkey Scripts", "AHK-Scripts", "autohotkey-old" — probably related.
  → River says: "These folders might be the same thing. Combine?"

WEIGHT 6 — THEME CLUSTERS
  Multiple folders with the same dominant file type scattered around.
  12 folders all containing .py files. 8 folders all containing .md files.
  → River says: "These are scattered but related. Create a hub?"

WEIGHT 5 — TINY/EMPTY FOLDERS
  Folders with 0-2 files, or completely empty.
  → River says: "This folder is nearly empty. Keep, merge, or delete later?"

WEIGHT 4 — OLD INACTIVE
  Folders not modified in 6+ months.
  → River says: "Nothing has changed here in a while."

WEIGHT 3 — LARGE SPACE USERS
  Individual files or folders consuming disproportionate space.
  → River says: "This is taking up a lot of room. Worth reviewing."
```

---

## How simple mode should walk through this

NOT a dump of 602 finding cards.
Show ONE BLOCK AT A TIME, grouped by weight, highest first.

### The guided flow (what the user sees)

```
STEP 1: SAFETY CHECK
  ┌─────────────────────────────────────────┐
  │ 🛡️ Protected items found               │
  │                                         │
  │ River found 1 system folder and 11      │
  │ project seeds. These are marked         │
  │ protected — they will not be moved,     │
  │ renamed, or archived.                   │
  │                                         │
  │ • _gsdata_ (system folder)              │
  │ • 11 folders with README.md             │
  │                                         │
  │ [✓ River approved — no action needed]   │
  │                                         │
  │ Status: AUTO-APPROVED (safe)            │
  └─────────────────────────────────────────┘
  [Continue to next finding →]
```

```
STEP 2: DUPLICATES
  ┌─────────────────────────────────────────┐
  │ 📋 3 duplicate file groups found        │
  │                                         │
  │ Same content, different locations.       │
  │                                         │
  │ Group 1:                                │
  │   config.json (2.1 KB)                  │
  │   📁 A/project-1/config.json            │
  │   📁 A/backup/config.json               │
  │                                         │
  │ [Keep first] [Keep second] [Keep both]  │
  │ [Send all to duplicate review]          │
  └─────────────────────────────────────────┘

STEP 3: BAD NAMES
  ┌─────────────────────────────────────────┐
  │ 🏷️ 32 files need renaming              │
  │                                         │
  │ Pick a naming schema first:             │
  │                                         │
  │ [Baseline]  [Date First]  [PARA]        │
  │                                         │
  │ Baseline: lowercase + hyphens           │
  │   "My Report FINAL.docx"               │
  │   → "my-report-final.docx"             │
  │                                         │
  │ Date First: YYYY-MM-DD prefix           │
  │   "My Report FINAL.docx"               │
  │   → "2026-06-14-my-report-final.docx"  │
  │                                         │
  │ PARA: Projects/Areas/Resources/Archive  │
  │   "My Report FINAL.docx"               │
  │   → "projects-my-report-v01.docx"      │
  │                                         │
  │ ────────────────────────────────────     │
  │ Preview (first 10 of 32):               │
  │                                         │
  │ OLD                    → NEW            │
  │ Auto Hot Key NEW       → autohotkey-new │
  │ AAA Programming        → programming   │
  │ My Notes (copy).txt    → my-notes.txt  │
  │                                         │
  │ [Approve all 32] [Review one by one]    │
  │ [Skip renaming]                         │
  └─────────────────────────────────────────┘

STEP 4: ORGANIZATION OPPORTUNITIES
  ┌─────────────────────────────────────────┐
  │ 📁 6 organization suggestions           │
  │                                         │
  │ 1. 4 scattered AutoHotkey folders       │
  │    → Suggest: Create "AutoHotkey Hub"   │
  │    [Create Hub] [Skip]                  │
  │                                         │
  │ 2. 3 empty folders found                │
  │    → Suggest: Delete later              │
  │    [Send to quarantine] [Keep] [Skip]   │
  │                                         │
  │ 3. 27 archive/export leftovers          │
  │    → Suggest: Move to _archive          │
  │    [Archive all] [Review] [Skip]        │
  │                                         │
  │ 4. 157 folders missing metadata         │
  │    → Suggest: Generate .folderbrain     │
  │    [Generate all] [Skip]                │
  │                                         │
  └─────────────────────────────────────────┘
```

```
STEP 5: SUMMARY
  ┌─────────────────────────────────────────┐
  │ ✅ Intelligence sort complete            │
  │                                         │
  │ River reviewed 602 finding cards.       │
  │                                         │
  │ ✓ 12 items auto-protected              │
  │ ✓ 3 duplicate groups flagged           │
  │ ✓ 32 renames approved (baseline)       │
  │ ✓ 1 hub created (AutoHotkey)           │
  │ ✓ 3 empty folders sent to quarantine   │
  │ ○ 27 archive items skipped             │
  │ ○ 157 metadata generation skipped      │
  │ ○ 240 unknown files deferred           │
  │                                         │
  │ [View full report] [Back to home]       │
  └─────────────────────────────────────────┘
```

---

## Approval status badges

Every finding block should show ONE of these:

```
[✓ RIVER AUTO-APPROVED]    — safe items, weight 10, no user action needed
[✓ YOU APPROVED]           — user clicked approve
[○ SKIPPED]                — user clicked skip
[✗ DISAPPROVED]            — user rejected the suggestion
[→ DEFERRED]               — user said "not now, come back later"
```

Color coding:
- Green = approved (River or user)
- Gray = skipped
- Red = disapproved
- Amber = deferred

When user DISAPPROVES, the next action should be offered:
```
You disapproved: "Rename 32 files using baseline schema"

Alternative actions:
  [Review one by one]
  [Try a different naming schema]
  [Skip renaming entirely]
  [Send to manual review queue]
```

---

## Default naming schemas (out of the box)

River should ship with 3 naming schemas anyone can use:

### 1. Baseline (default)
```
Rule: lowercase + hyphens + remove special chars
"My Report FINAL (2).docx" → "my-report-final-2.docx"
Best for: quick cleanup, universal
```

### 2. Date First
```
Rule: YYYY-MM-DD + lowercase slug
"My Report FINAL.docx" → "2026-06-14-my-report-final.docx"
Best for: chronological filing, journals, logs
```

### 3. Domain + Topic
```
Rule: DOMAIN__TOPIC__TYPE.ext
"entropy research notes.md" → "theophysics__entropy-research__notes.md"
Best for: classified filing, research, project work
Requires: classification pass first
```

### 4. Custom (user defines pattern)
```
Available tokens: {date} {domain} {slug} {seq} {version} {ext}
User builds: "{date}__{domain}__{slug}__v{version}.{ext}"
```

The naming schema picker should appear BEFORE any rename preview.
User picks once, it applies to all renames in that session.

---

## What Codex should build

### In simple.html "Let intelligence sort" flow:

1. Replace the flat card dump with STEP-BY-STEP blocks
2. Group findings by weight tier (10, 9, 8, 7, 6, 5, 4, 3)
3. Show one tier at a time with approve/skip/disapprove buttons
4. Auto-approve weight 10 items (show as "River auto-approved")
5. Add naming schema picker before the rename step
6. Show running summary at the bottom (approved/skipped/deferred counts)
7. End with a completion card showing everything that happened
8. Each block gets a status badge (approved/skipped/disapproved/deferred)
9. Disapproval triggers alternative action suggestions
10. All decisions log to SQLite action_log with the 5-digit action codes

### New API endpoints needed:

```
GET  /api/findings?root=...&min_weight=5
     → returns finding cards grouped by weight tier

POST /api/findings/decide
     → { finding_id, action: "approve|skip|disapprove|defer", schema: "baseline" }
     → logs to action_log, updates finding status
```

---

## The core rule

The intelligence sort should answer ONE question:

> "What are the safest, highest-value cleanup opportunities in this folder?"

Not 602 suggestions. The top 5-10 grouped by type, walked through one at a time,
with approval at every step and River explaining why it thinks each one matters.


---

## Pre-loaded defaults (ship out of the box)

### Default domains (generic — works for anyone)

```
documents       — reports, letters, memos, PDFs, Word docs
development     — code, scripts, configs, repos, packages
media           — photos, videos, audio, graphics, screenshots
personal        — invoices, receipts, tax, insurance, IDs
business        — marketing, sales, proposals, contracts
reference       — manuals, guides, tutorials, wikis, bookmarks
creative        — writing, art, design, drafts, sketches
data            — spreadsheets, CSVs, databases, exports
communication   — emails, chat logs, transcripts, meeting notes
system          — configs, logs, caches, temp files, backups
```

These 10 cover 90% of what any person has on their computer.

### David's extended domains (loaded from config, not hardcoded)

```
theophysics     — framework research, papers, axioms, proofs
brain_system    — NLP pipeline, stations, models, watchers
trading         — stocks, options, charts, financial data
infrastructure  — NAS, Proxmox, Docker, networking, servers
lean            — formal proofs, Lean 4, Mathlib, tactics
ai_research     — LLM, transformers, embeddings, training
electrical      — wiring, circuits, panels, conduit, NEC
```

### How domains load

```
1. System ships with 10 generic defaults
2. User's config/domains.json adds or overrides
3. NLP classification uses whatever domains are loaded
4. New domains can be created from the "Custom" option in Q3
5. River learns which domains the user actually uses
```

### Default naming schemas (pre-loaded)

```
baseline        "my-report-final.docx"                    — always available
date_first      "2026-06-14-my-report-final.docx"         — chronological
domain_topic    "documents__my-report__final.docx"         — classified
johnny_decimal  "20.01-my-report-final.docx"               — JD system
para            "projects__my-report__v01.docx"            — PARA method
```

### The Q2 rename step uses these directly

When user picks "Clean names" in Q1, Q2 shows:

```
Pick a naming style:

[Baseline]        lowercase + hyphens (recommended for first pass)
[Date First]      YYYY-MM-DD prefix
[Domain + Topic]  domain__topic__type
[Browse more]     Johnny Decimal, PARA, Custom...
```

First three are always visible. "Browse more" expands to show
Johnny Decimal, PARA, and a custom pattern builder.

No configuration needed. Pick one and go.

---

## The 3×3 decision tree (final spec for Codex)

```
QUESTION 1: What's the goal?
├── 🏷️  Clean names
├── 📁  Organize structure  
└── 📦  Relocate / archive

QUESTION 2: Which action?
├── Clean names →  [Baseline] [Date First] [Domain+Topic] [More...]
├── Organize →     [Combine]  [Separate]   [Link/Hub]
└── Relocate →     [Move]     [Archive]    [Delete Later]

QUESTION 3: For each item, 3 suggestions + custom
├── [1] Rules engine suggestion
├── [2] River recommendation (highlighted, with confidence %)
├── [3] NLP suggestion
└── [4] None of these — type the correct answer

Every Q3 decision saves to preference engine:
  { options_shown, river_recommended, user_selected, was_custom, timestamp }
```

River auto-approves weight 10 items silently.
Weight 9+ items get the full 3-suggestion treatment.
Weight 5 and below are batched: "47 low-priority items — approve all / review"


---

## Rename review sampling (final spec)

### Sample sizes by batch

```
1 - 100        → show all
101 - 1,000    → show 100
1,001 - 10,000 → show 200
10,001-100,000 → show 300
100,000+       → show 500 max
```

### Sample composition (not random — weighted smart sample)

```
1. WEIRDEST FIRST (red highlight, always at top)
   ALL CAPS, symbols, very long names, duplicates,
   collision risks, UUID/hash, "final final copy 2",
   missing extension, strange extension.
   These go first. Different color. Non-negotiable review.

2. ALPHABET COVERAGE
   A few from each starting letter A-Z, plus 0-9 and symbols.
   Catches schema doing something weird to a specific range.

3. EXTENSION COVERAGE
   At least one from each file type: .pdf, .docx, .py, .md, .xlsx, etc.
   Don't let one extension dominate the sample.

4. FOLDER COVERAGE
   At least one from each parent folder.
   Don't let one folder dominate the sample.

5. RANDOM FILL
   Remaining slots filled randomly to catch ordinary-looking mistakes.
```

### Display rules

```
- Weird names: highlighted with amber/red background, shown FIRST
- Clean names that wouldn't change: show a few as "✓ already clean"
- Editable new-name cells: click to override, override = training data
- Count badge updates live: "Approve 287 of 300 sampled renames"
```

### Approval options

```
[Approve sampled only]           — rename only the 300 you reviewed
[Approve all matching schema]    — apply schema to full 100,000 batch
[Review another sample]          — pull a fresh smart sample
[Filter by extension/folder]     — narrow what you're looking at
[Cancel]                         — nothing happens
```

### Large batch confirmation gate

For "Approve all matching schema" on 10,000+ files:

```
┌───────────────────────────────────────────┐
│  ⚠  BATCH RENAME CONFIRMATION             │
│                                           │
│  This will rename 100,000 files.          │
│  You reviewed 300 sampled examples.       │
│  Schema: Baseline (lowercase + hyphens)   │
│                                           │
│  3 corrections were made in the sample.   │
│  River applied those corrections to the   │
│  remaining 99,700 files.                  │
│                                           │
│  [Confirm rename all]  [Go back]          │
└───────────────────────────────────────────┘
```

### River learning from sample corrections

Every edit in the sample teaches River:

```json
{
  "original": "AAA Progaimng Folder New",
  "schema_suggested": "aaa-progaimng-folder-new",
  "user_corrected": "programming-folder",
  "correction_type": "removed_priority_hack + fixed_typo + removed_adjective",
  "apply_similar": true
}
```

River scans the remaining 99,700 for files matching the same
patterns (priority hacks, typos, trailing adjectives) and applies
the learned correction before executing.

Sample corrections propagate. That's the power of reviewing 300
instead of 100,000 — your 3 fixes become 3,000 fixes.
