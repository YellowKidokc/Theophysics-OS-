# File Sorter Hub Merge Map

This folder is now the working unified app shell.

## Active Shell

- `api_server.py` runs the local API on `http://127.0.0.1:8450`.
- `index.html` is the browser GUI.
- `LAUNCH_FILE_SORTER_GUI.bat` starts the API and opens the GUI.
- `hub_engines.py` is the integration layer for the included systems.
- `sorter_cache.py` writes scan runs, file records, classifications, and decisions to `\\192.168.2.50\brain\09_DATABASES\FIS\sorter_cache.sqlite`.
- The Cache page scans folder inventory into SQLite so the app can load known names, folders, extensions, and sizes without rescanning the drive on every page open.
- Cache classifications feed the same Sort review screen, so approve/reject/override decisions train the preference engine from cached files too.
- Theme clusters use cached files to find repeated patterns across folders, such as PDFs, ebooks, images, programming, AutoHotkey, or learned domains.
- `INTELLIGENT_FILE_SYSTEM_RULES.md` holds the first normalize/alias/cluster/decision rules from the clipboard notes.
- `APPROVAL_AND_METADATA_RULES.md` holds the JSON sidecar and recommendation-panel rules.
- `\\192.168.2.50\brain\09_DATABASES\FIS\sorter_cache.sqlite` is the GUI/cache/action journal. It stores A/B/C roots and five-digit action codes such as `00001`.
- `\\192.168.2.50\brain\09_DATABASES\FIS\preference_engine.db` is the learning database. Approve/reject/override decisions update its Markov chains.
- Set `FIS_DATABASE_DIR` before launch only if this shared database folder ever needs to move.
- Folder sidecars are written as `.folderbrain.json` and only contain compact summaries; SQLite remains the evidence store.

## Integrated Engines

### File Sorter v3

Status: active

Used for the current scan, classify, naming preview, decision recording, and preference learning workflow.

Current rename baseline:

- every file can be previewed as lowercase + hyphenated + lowercase extension
- `/api/rename/baseline-plan` returns a dry-run plan with rename, already-clean, and collision states
- no rename is applied until an explicit review/apply gate is added

### File Intelligence System

Status: available, optional heavy features

Useful pieces to absorb next:

- richer NLP classification pipeline
- rename queue concepts
- browser/hotkey capture ideas
- Behavioral Intelligence Layer concepts

Keep optional until Postgres and NLP dependencies are intentionally configured.

### Local File Organizer

Status: available, lightweight preview integrated

Useful pieces to absorb next:

- document/text readers
- image/document organization concepts
- dry-run operation planning

Model-driven organizing still depends on Nexa/Tesseract and should stay optional until the environment is ready.

## Do Not Delete Yet

- `file-intelligence-system-master`
- `Local-File-Organizer-main`
- `file-sorter-gui-v2.jsx`
- `file-sorter-v3.jsx`

Retire these only after the hub has equivalent routes and GUI controls.

## Next Merge Steps

1. Replace the single-file HTML GUI with a cleaner app structure.
2. Add a real hub sidebar or tabs.
3. Move shared file readers into one `engines` package.
4. Add safe dry-run organize actions before any move/rename action.
5. Add Brain Hub job-card export.
6. Promote SQLite cache scans into a background worker so the Home screen can warm itself continuously.
7. Add saved scan roots after the first real folders are chosen.
