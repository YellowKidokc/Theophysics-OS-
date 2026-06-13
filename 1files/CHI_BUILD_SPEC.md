# BUILD SPEC: .chi Folder Metadata + Learning File Classifier
## POF 2828 | June 11, 2026
## Handoff to: Claude Code / Codex / Any AI with filesystem access

---

## WHAT WE'RE BUILDING

Three connected components:

1. **`.chi` folder sidecar generator** — drops a `_folder.chi` metadata file in every folder
2. **Learning file classifier** — Markov chain + LLM fallback that gets better at naming/classifying over time
3. **Scheduled automation** — bat/task that runs nightly to keep metadata fresh

All code goes in `D:\GitHub\organize\`. Database is `D:\GitHub\organize\organize.db` (already exists with tables: drives, files, snapshots, actions, batches).

---

## COMPONENT 1: .chi Sidecar Generator

### The file: `_folder.chi`

Extension `.chi` is custom. Content is markdown with YAML frontmatter. One per folder.

```yaml
---
primary_chi: K
secondary_chi: [G, E]
role: repo
domain: theophysics
tags: [lean, formal-proof, law-09]
state: W
risk: R2
file_count: 47
total_size_mb: 12.3
extensions: {".lean": 28, ".md": 15, ".toml": 4}
last_scanned: 2026-06-11T03:45:00
created_by: chi-generator
location_history:
  - path: "D:\\GitHub\\atlas-lean"
    date: 2026-06-11
notes: ""
---

# D:\GitHub\atlas-lean

## Contents
- 28 .lean files
- 15 .md files  
- 4 .toml files

## Auto-detected Role
repo, lean_project, theophysics

## Classification Confidence
72% — below threshold, needs human review
```

### Script: `chi_generator.py`

```
python chi_generator.py scan D:\GitHub          # generate stubs for all subfolders
python chi_generator.py scan D:\GitHub --update  # update existing, create missing
python chi_generator.py read D:\GitHub\atlas-lean  # read and print a folder's .chi
```

**Behavior:**
- Walk every subfolder (configurable depth, default 3)
- If `_folder.chi` exists: update file_count, total_size, extensions, last_scanned. DO NOT overwrite human-edited fields (tags, notes, primary_chi if already set)
- If `_folder.chi` missing: create stub with auto-detected values
- Skip folders that start with `.` (except `.obsidian`)
- Skip `node_modules`, `__pycache__`, `.git` internals (but detect `.git` presence as a marker)

**Auto-detection rules (same as engine.py detect_role):**
- `.git` in children → role: repo
- `.obsidian` in children → role: obsidian
- `package.json` → role: node_project  
- `pyproject.toml` / `setup.py` / `requirements.txt` → role: python_project
- `Cargo.toml` → role: rust_project
- `lakefile.lean` → role: lean_project
- Path contains `faiththruphysics|theophysics|logos_v|mda-build|genesis_to_quantum|gtq` → domain: theophysics
- 50%+ HTML files and 5+ files → role: html_output

**χ factor auto-detection (best-effort, low confidence):**
- role=repo + domain=theophysics → primary_chi: K (knowledge/code)
- role=obsidian → primary_chi: K (structured claims)
- role=html_output + domain=theophysics → primary_chi: E (truth/signal publication)
- role=lean_project → primary_chi: K or C (formal proofs)
- Heavy `.xlsx`/`.csv` → primary_chi: T or S (data/measurement)
- If confidence < 70%, mark `needs_review: true` in frontmatter

### Database addition

Add to organize.db:

```sql
CREATE TABLE IF NOT EXISTS chi_metadata (
    id INTEGER PRIMARY KEY,
    folder_path TEXT UNIQUE NOT NULL,
    primary_chi TEXT DEFAULT '',
    secondary_chi TEXT DEFAULT '',  -- JSON array as string
    role TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    tags TEXT DEFAULT '',           -- JSON array as string
    state TEXT DEFAULT 'W',
    risk TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    needs_review INTEGER DEFAULT 1,
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    extensions TEXT DEFAULT '',     -- JSON object as string
    chi_file_exists INTEGER DEFAULT 0,
    last_scanned TEXT,
    last_human_edit TEXT,
    created TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chi_folder ON chi_metadata(folder_path);
CREATE INDEX IF NOT EXISTS idx_chi_primary ON chi_metadata(primary_chi);
CREATE INDEX IF NOT EXISTS idx_chi_domain ON chi_metadata(domain);
```

---

## COMPONENT 2: Learning File Classifier

### The learning loop

```
File arrives → Lookup table (instant) → Confidence check
  ├─ Above 85% → auto-classify, log result
  └─ Below 85% → LLM call → suggest → David reviews → feedback into lookup
```

### Database tables

```sql
CREATE TABLE IF NOT EXISTS classification_rules (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT NOT NULL,     -- 'extension', 'keyword', 'path', 'content'
    pattern TEXT NOT NULL,          -- the match pattern
    primary_chi TEXT NOT NULL,      -- suggested χ factor
    weight REAL DEFAULT 1.0,       -- Markov weight (increases with use)
    hit_count INTEGER DEFAULT 0,   -- times this rule matched
    accept_count INTEGER DEFAULT 0, -- times David accepted this suggestion
    reject_count INTEGER DEFAULT 0, -- times David overrode this
    created TEXT DEFAULT (datetime('now')),
    UNIQUE(pattern_type, pattern, primary_chi)
);

CREATE TABLE IF NOT EXISTS classification_history (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    suggested_chi TEXT,
    accepted_chi TEXT,             -- what David actually picked
    confidence REAL,
    method TEXT,                   -- 'rule', 'markov', 'llm', 'manual'
    created TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rules_pattern ON classification_rules(pattern_type, pattern);
CREATE INDEX IF NOT EXISTS idx_history_file ON classification_history(file_name);
```

### Seed rules (bootstrap the Markov chain)

```python
SEED_RULES = [
    # Extension rules
    ("extension", ".lean", "K", 0.8),
    ("extension", ".md", "K", 0.5),
    ("extension", ".html", "E", 0.6),
    ("extension", ".xlsx", "T", 0.5),
    ("extension", ".csv", "T", 0.5),
    ("extension", ".pdf", "K", 0.4),
    ("extension", ".py", "M", 0.6),
    ("extension", ".js", "M", 0.6),
    ("extension", ".ts", "M", 0.6),
    ("extension", ".rs", "M", 0.6),
    ("extension", ".sql", "K", 0.5),
    ("extension", ".png", "E", 0.3),
    ("extension", ".mp3", "E", 0.4),
    ("extension", ".mp4", "E", 0.4),
    
    # Keyword rules  
    ("keyword", "grace", "G", 0.8),
    ("keyword", "entropy", "S", 0.9),
    ("keyword", "decay", "S", 0.8),
    ("keyword", "moral", "F", 0.7),
    ("keyword", "logos", "K", 0.9),
    ("keyword", "trinity", "C", 0.8),
    ("keyword", "coherence", "C", 0.9),
    ("keyword", "quantum", "Q", 0.8),
    ("keyword", "faith", "Q", 0.7),
    ("keyword", "love", "R", 0.8),
    ("keyword", "covenant", "R", 0.9),
    ("keyword", "timeline", "T", 0.9),
    ("keyword", "prophecy", "T", 0.7),
    ("keyword", "signal", "E", 0.8),
    ("keyword", "truth", "E", 0.8),
    ("keyword", "alignment", "M", 0.8),
    ("keyword", "dashboard", "M", 0.7),
    ("keyword", "pipeline", "M", 0.8),
    ("keyword", "watcher", "M", 0.7),
    ("keyword", "atonement", "F", 0.9),
    ("keyword", "sin", "F", 0.8),
    ("keyword", "master_equation", "CHI", 0.95),
    ("keyword", "chi", "CHI", 0.7),
    
    # Path rules
    ("path", "LOGOS", "K", 0.85),
    ("path", "MDA", "S", 0.8),
    ("path", "GTQ", "E", 0.7),
    ("path", "LEAN", "K", 0.8),
    ("path", "GitHub", "M", 0.5),
    ("path", "Obsidian", "K", 0.6),
]
```

### Classifier script: `classifier.py`

```
python classifier.py classify "D:\GitHub\atlas-lean\Noether.lean"
  → K (confidence: 92%, method: rule+keyword)

python classifier.py classify "D:\some\random\budget.xlsx"  
  → T (confidence: 45%, method: rule) — BELOW THRESHOLD
  → LLM suggests: T+K "time-series financial data"
  → Awaiting review

python classifier.py review          # show all pending reviews
python classifier.py accept 42 S     # accept suggestion 42, override to S
python classifier.py train           # recalculate Markov weights from history
python classifier.py export          # dump rules + history to Excel for bulk review
python classifier.py import rules.xlsx  # import corrected rules from Excel
```

### LLM fallback (when confidence < threshold)

```python
import anthropic

def llm_classify(filename, content_preview, path):
    client = anthropic.Anthropic()  # key from env
    
    CHI_FACTORS = """
    G — Gravity/Grace/Authority: foundation, substrate, canonical authority, source
    M — Motion/Alignment/Mechanism: process, workflow, causal machinery, tools
    E — Truth/Signal: truth, deception, signal fidelity, Shannon, publication, light
    S — Entropy/Judgment/Decay: disorder, repair, thermodynamic correction, decline
    T — Time/Sequence: timeline, prophecy, before/after, version order, temporal data
    K — Knowledge/Logos/Information: definitions, equations, compression, structured claims
    R — Relation/Binding: covenant, love, dependency, relational structure, connection
    Q — Quantum/Faith: uncertainty, collapse, commitment, observer, faith under uncertainty  
    F — Weak/Sin Conservation: atonement, deficit, displacement, hidden moral debt
    C — Coherence/Christ: integration, whole-system unity, no-drift topology
    CHI — Master Integration: full synthesis, all-law maps, whole-framework
    """
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{
            "role": "user", 
            "content": f"""Classify this file by which chi factor it most serves.

Filename: {filename}
Path: {path}
Content preview: {content_preview[:500]}

Chi factors:
{CHI_FACTORS}

Respond in JSON only:
{{"primary": "X", "secondary": ["Y","Z"], "confidence": 0.XX, "reason": "brief reason"}}"""
        }]
    )
    return response.content[0].text
```

---

## COMPONENT 3: Scheduled Automation

### File: `chi_nightly.bat`

Drop in Windows Task Scheduler or Startup folder.

```bat
@echo off
title CHI Nightly Scan
cd /d D:\GitHub\organize

echo [%date% %time%] Starting nightly chi scan...

REM Update .chi files in key locations
python chi_generator.py scan D:\GitHub --update --depth 2
python chi_generator.py scan D:\LOGOS_V5 --update --depth 3
python chi_generator.py scan D:\BIL --update --depth 2

REM Run classifier training on any new history
python classifier.py train

REM Update organize.db snapshots
python engine.py scan D:\GitHub repo dev

echo [%date% %time%] Nightly scan complete.
```

### Task Scheduler setup:
- Trigger: Daily at 3:00 AM
- Action: Run `D:\GitHub\organize\chi_nightly.bat`
- Condition: Only when on AC power
- Settings: Stop if running longer than 30 minutes

---

## FILE STRUCTURE WHEN DONE

```
D:\GitHub\organize\
  engine.py           ← existing scan/reconcile engine
  server.py           ← existing HTTP API + HTML server  
  index.html          ← existing browser UI
  organize.db         ← SQLite brain (existing + new tables)
  chi_generator.py    ← NEW: .chi sidecar generator
  classifier.py       ← NEW: learning file classifier
  chi_nightly.bat     ← NEW: scheduled automation
  seed_rules.json     ← NEW: bootstrap classification rules
  README.md           ← NEW: usage docs
```

---

## χ FACTOR QUICK REFERENCE (for the helper panel)

| Code | Name | Filing Meaning | Put files here when they serve... |
|------|------|----------------|-----------------------------------|
| G | Gravity/Grace | Foundation, authority | Grace, substrate, canonical authority, law/order |
| M | Mechanism/Alignment | Process, tools | Workflows, causal machinery, M_eff, pipelines |
| E | Truth/Signal | Signal fidelity | Truth, Shannon, publication, Bible-as-signal |
| S | Entropy/Judgment | Decay repair | Disorder, judgment, thermodynamic correction |
| T | Time/Sequence | Timeline, order | Prophecy, sequence, before/after, temporal data |
| K | Knowledge/Logos | Information | Definitions, equations, compression, structured claims |
| R | Relation/Binding | Connection | Covenant, love, dependency graphs, relational |
| Q | Quantum/Faith | Uncertainty | Collapse, commitment, observer, faith |
| F | Weak/Sin | Conservation | Atonement, deficit, displacement, moral debt |
| C | Coherence/Christ | Integration | Whole-system unity, no-drift topology |
| CHI | Master Integration | Full synthesis | All-law maps, Master Equation, whole-framework |

---

## FILENAME PATTERN

```
PRIMARYVAR__ENTITY__STATE__DATE__SHORTCODE.ext
```

Examples:
```
G__GRACE_EXTERNALITY__F__20260610__L01.md
S__CORRECTED_ENTROPY_KERNEL__F__20260610__SEFF.lean
K__LOGOS_INFORMATION_SHANNON__W__20260610__LAW06.md
CHI__MASTER_EQUATION_KERNEL__F__20260610__MEK.md
```

States: W=Working, F=Final/Formal, A=Archive, D=Deprecated
Risk: R1=Low, R2=Moderate, R3=High interpretive, R4=Canon-sensitive

---

## ACCEPTANCE CRITERIA

- [ ] `python chi_generator.py scan D:\GitHub` creates `_folder.chi` in every subfolder
- [ ] Existing `_folder.chi` files are updated (counts, dates) without overwriting human edits
- [ ] `python classifier.py classify <file>` returns a χ factor with confidence
- [ ] Below-threshold files trigger LLM call and get queued for review
- [ ] `python classifier.py review` shows pending items
- [ ] `python classifier.py accept <id> <chi>` logs the decision and updates Markov weights
- [ ] `python classifier.py export` dumps to Excel for bulk review
- [ ] Nightly bat runs without errors
- [ ] organize.db has chi_metadata and classification_rules tables populated

---

*Build spec v1.0 | June 11, 2026 | POF 2828*
*Origin: Claude (Opus) session — architecture from David + Claude, UI feedback from GPT*
*Engine already deployed at D:\GitHub\organize\engine.py*
