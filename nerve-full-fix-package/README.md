# Nerve Full Fix Package

Created: 2026-04-09
Purpose: give an external fixer the real code and runtime files needed to diagnose and repair Nerve TTS.
Source repo: https://github.com/YellowKidokc/nerve/tree/main

## Included
- Full GitHub repo snapshot in `repo/`
- Live running Nerve HTML in `live_install/html/`
- Live binary and voice cache in `live_install/runtime/`
- Live persisted config in `live_install/config/`
- Theophysics TTS pipeline scripts/config/launchers in `tts_pipeline/`
- Existing notes and session logs in `notes/`

## Deliberate Exclusions
- WebView2 cache/profile directories were excluded because they are large, machine-specific, and not required for source-level TTS repair.
- Full Python venv contents were excluded for the same reason.

## Most Relevant Files
- `repo/src/tts.rs`
- `repo/src/main.rs`
- `repo/src/config.rs`
- `repo/src/panels.rs`
- `repo/html/settings.html`
- `live_install/html/settings.html`
- `live_install/html/tts-engine.html`
- `live_install/config/config.json`
- `live_install/runtime/voice_cache.json`

## Repo vs Live HTML Drift
- Repo HTML files: 3
- Live HTML files: 22
- Live-only HTML:
  - 7q-engine.html
  - chat.html
  - clipboard3.html
  - dashboard.html
  - hub.html
  - links.html
  - nexus-dashboard.html
  - prompt_picker.html
  - prompts.html
  - research_links.html
  - research.html
  - task-calendar.html
  - task-merger-20260325.html
  - task-merger-20260328.html
  - task-merger-20260329.html
  - task-merger-20260330.html
  - task-merger-20260401.html
  - theophysics-hub.html
  - tts-engine.html

## Working Theory
- The TTS bug may live in the Rust backend, the live HTML, or the gap between GitHub `main` and the installed ClipSync files.
- This package preserves all three surfaces.
