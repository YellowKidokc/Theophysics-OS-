---
type: AI_SESSION
status: complete
agent: "Claude Opus 4.6"
date: 2026-04-04
session_id: "20260404_OPUS_NerveClipSyncDev"
vault_links:
  - github_repo: "YellowKidokc/nerve"
  - nerve_working_dir: "C:\\Users\\lowes\\AppData\\Local\\Programs\\Warp"
  - edge_tts_dir: "O:\\999_IGNORE\\TTS_Engines\\Edge TTS\\"
confidence_score: 82
weakest_link: "WebView2 custom protocol fix (nerve://) deployed but not yet confirmed working by user — settings tabs may still be broken"
---

# AI Session Log — Nerve/ClipSync Agent: AI Integration, Clipboard Redesign, WebView2 Fix, Edge TTS

---

## THREAD STATE (read this first)

> **The next AI reads this section BEFORE anything else.**

### RESOLVED (Floor — these hold, don't re-derive)
- **AI module added to nerve** (`src/ai.rs`) — Claude API, OpenAI-compatible API (also covers LM Studio, Ollama), provider/workflow config in `src/config.rs`, IPC handlers in `src/main.rs`
- **Clipboard panel completely redesigned** (`html/clipboard.html`) — long/skinny layout (460×1080), 4 tabs (HOTKEYS 1-50 / HISTORY / AI / SAVED), 2-column card grid, bottom dock with Docs/Video/Music/Pics categories, 2 draggable pins, pencil (pin-external), bigger fonts
- **Pin External Window** implemented (`src/window_mgmt.rs`) — uses Windows API `GetForegroundWindow`/`SetWindowPos` to toggle `HWND_TOPMOST`, IPC handler `pin_external` in main.rs spawns thread with 1.5s delay
- **Window close (X button) fixed** — added `CloseRequested` handler in main event loop that calls `panel_mgr.hide_by_window_id()` instead of doing nothing
- **Custom protocol (nerve://)** implemented in `src/panels.rs` — replaces `file://` URLs that WebView2 blocks JavaScript on. Uses `with_custom_protocol("nerve", ...)` to serve HTML files from `Config::html_dir()`
- **Edge TTS pipeline fully repaired** — created Python venv at `C:\Users\lowes\Documents\Theophysics Master\.venv_edge\`, installed `edge-tts`, wrote `safe_edge_tts.py` with 5.5× speed support (Edge TTS at +100% rate + ffmpeg atempo chains for remaining 2.75×)
- **Successfully converted test file** at 5.5× speed: "I Didn't Write the Math. I Found It." → MP3
- **Pushed to GitHub** — commit 146286c to YellowKidokc/nerve (AI integration, clipboard redesign, pin-external, window close fix)

### OPEN (Active questions, vulnerabilities, unfinished chains)
- **WebView2 custom protocol NOT confirmed working** — nerve:// protocol was deployed to fix settings tabs (and all panel JS), but user hasn't tested yet. This is the #1 thing to verify next session.
- **Custom protocol commit NOT pushed** — the nerve:// fix in `panels.rs` was made AFTER the GitHub push. Needs a follow-up push.
- **Chat panel (`html/chat.html`)** exists but is minimal — just a textarea + provider/workflow dropdowns. Needs refinement for the workflow-based interface David wants.
- **Pencil drag-to-pin** not implemented — user wanted to drag the pencil icon onto another window to pin it. Current implementation just pins the foreground window after 1.5s delay. David said "don't worry about the pencil" for now.
- **Saved tab persistence** uses localStorage — works but data is per-origin. May need backup/sync strategy.
- **Config.json override issue** — old saved config.json overrides new Rust defaults. Had to manually edit config.json to update clipboard dimensions. The `normalize()` function in config.rs should handle this better.

### NEXT SESSION (Priority-ordered, specific)
1. **Verify nerve:// custom protocol works** — launch nerve, open settings panel, confirm tabs are clickable and JS runs
2. **Push custom protocol fix to GitHub** — the panels.rs changes with nerve:// aren't in the remote yet
3. **Test all panel functionality** — clipboard hotkeys, history, AI tab, bottom dock categories
4. **Refine AI workflow interface** — "Extract Links" and "Lossless Summary" workflows that process documents through AI
5. **Bottom dock sync** — Docs/Video/Music/Pics categories need actual file browsing/syncing behavior

---

## STATE ON ARRIVAL

David had the nerve/ClipSync Agent project at `C:\Users\lowes\AppData\Local\Programs\Warp` — a Rust desktop app using tao (windowing), wry (WebView2), tray-icon, and global-hotkey. The app had basic clipboard functionality, settings panel, and tray integration. David wanted AI integration, a redesigned clipboard panel, and several UX fixes. The Edge TTS pipeline at `O:\999_IGNORE\TTS_Engines\Edge TTS\` was also broken and needed repair.

---

## GOAL

Add AI provider support (Claude/OpenAI/Local LLM) with workflow-based interface to nerve, completely redesign the clipboard panel (long/skinny, 3 tabs, bottom dock, bigger fonts), fix window close behavior, fix WebView2 JavaScript execution, repair Edge TTS pipeline with 5.5× speed, push to GitHub.

---

## ANCHORS (Structural Insights — the new stuff)

1. **WebView2 blocks JS on file:// URLs:** This was the root cause of settings tabs not responding to clicks. WebView2 treats `file:` URLs as unique security origins and blocks script execution. The fix is a custom protocol (`nerve://localhost/`) that serves the same HTML files but from a trusted origin. This likely affects ALL panels, not just settings.

2. **Edge TTS caps at 2× speed:** The `rate` parameter maxes out at `+100%`. For higher speeds (like 5.5×), a two-stage pipeline is needed: Edge TTS generates audio at 2× rate, then ffmpeg's `atempo` filter chains handle the remaining multiplier (2.75× in this case). The atempo filter chains at max 2.0× per stage for quality.

3. **IPC Architecture Pattern:** WebViews communicate with Rust via `window.chrome.webview.postMessage(JSON)` → Rust `handle_ipc()` dispatches by `type` field → responds via `panel_mgr.evaluate_script()`. Async operations (like AI chat) spawn threads and use `_eval` internal event to route responses back.

4. **Config persistence gotcha:** Saved `config.json` in `%APPDATA%\clipsync-agent\` always overrides compiled-in defaults. New fields get added via `normalize()`, but existing fields keep their old values. This means changing panel dimensions in Rust code has no effect if the user already has a saved config.

---

## OUTPUTS

### Computational
- Built and deployed nerve.exe with all new features
- Created Python venv and installed edge-tts package
- Converted test TTS file at 5.5× speed successfully

### Written
- `src/ai.rs` — NEW: AI API module (Claude + OpenAI-compatible endpoints)
- `src/config.rs` — MODIFIED: Added AiProvider, AiWorkflow, AiConfig structs with defaults
- `src/main.rs` — MODIFIED: AI IPC handlers, pin_external handler, CloseRequested handler
- `src/panels.rs` — MODIFIED: Custom nerve:// protocol, focus management, devtools enabled
- `src/window_mgmt.rs` — MODIFIED: Added pin_external_window() using Windows API
- `html/clipboard.html` — REWRITTEN: Complete redesign with 4 tabs, bottom dock, 2-column grid
- `html/chat.html` — NEW: Minimal AI chat panel
- `html/settings.html` — MODIFIED: Tab click fix (event→this parameter)
- `C:\Users\lowes\Documents\Theophysics Master\safe_edge_tts.py` — NEW: Edge TTS converter with speed multiplier
- `O:\999_IGNORE\TTS_Engines\Edge TTS\Convert-TTS.bat` — MODIFIED: Added SPEED=5.5 config

### Strategic / Decisions
- Custom protocol chosen over other WebView2 workarounds (virtual host, relaxed security) because it's the cleanest wry-native solution
- AI workflows preferred over raw chat — David wants structured prompts like "Extract Links" and "Lossless Summary", not open-ended conversation
- Edge TTS + ffmpeg two-stage approach chosen for speed over alternatives (pyttsx3, Coqui) because Edge TTS quality is superior

---

## PREDICTIONS & FALSIFICATION

| Prediction | Confirmation (Signal) | Falsification (Noise) |
|---|---|---|
| nerve:// protocol fixes all panel JavaScript | Settings tabs clickable, clipboard JS works, AI tab functional | Tabs still unresponsive after protocol change |
| Edge TTS 5.5× produces intelligible audio | User confirms audio is clear and usable at 5.5× | Audio is garbled or unintelligible at that speed |
| AI workflow approach is what David wants | David uses Extract Links / Lossless Summary workflows regularly | David abandons workflows and wants free-form chat instead |

---

## WHAT I GOT WRONG

- **Initially missed the WebView2 security origin issue** — spent multiple rounds trying to fix settings tabs with JS changes (event→this, error handling) when the real problem was that NO JavaScript was executing at all due to file:// origin restrictions.
- **Config override wasn't anticipated** — changed clipboard panel dimensions in Rust defaults, but the saved config.json kept the old values. Had to manually edit the config file.
- **Misunderstood David's size comment** — thought he wanted the clipboard panel resized when he was actually saying he liked the current size.

---

## TANGENT LOG (Compressed)

- **Tangent 1 (Pencil drag-to-pin):** David wanted to drag the pencil icon onto external windows to pin them. This is a complex feature requiring mouse capture outside the WebView. David deferred it: "don't worry about the pencil."
- **Tangent 2 (TTS while working on nerve):** David pivoted to fixing the Edge TTS pipeline mid-session. Separate from nerve but part of the same tooling ecosystem. Successfully repaired and enhanced with 5.5× speed.

---

## VARIABLE ALIGNMENT

> Which variables of χ were primarily engaged this session?

This session was **engineering/tooling work**, not direct Theophysics research. No χ variables were directly engaged. The work supports the research infrastructure:
- Edge TTS enables audio consumption of Theophysics documents
- nerve/ClipSync Agent with AI integration will enable workflow-based document processing (link extraction, lossless summaries) for research materials

---

## MEMORY CANDIDATES

> What should be written to persistent memory for future sessions?

- **nerve custom protocol requirement** — SOURCE: WebView2 file:// security block this session. IMPLICATIONS: All nerve HTML panels must use nerve:// protocol, not file:// URLs. Any new panels added must follow this pattern.
- **Edge TTS speed pipeline** — SOURCE: this session. IMPLICATIONS: safe_edge_tts.py at `C:\Users\lowes\Documents\Theophysics Master\` handles speeds >2× via two-stage Edge+ffmpeg. Venv at `.venv_edge`.

---

## TASKS CREATED / UPDATED

- [ ] Verify nerve:// custom protocol fixes panel JavaScript — launch and test settings tabs
- [ ] Push custom protocol fix to GitHub (YellowKidokc/nerve)
- [ ] Refine AI workflow interface — Extract Links and Lossless Summary workflows
- [ ] Bottom dock categories (Docs/Video/Music/Pics) — need actual file browsing behavior
- [ ] Config normalize() improvements — handle dimension/layout changes gracefully when defaults update

---

## LINKS

### Source Conversations
- This session (Claude Opus 4.6, April 4, 2026)

### Vault Files Created/Modified
- `C:\Users\lowes\AppData\Local\Programs\Warp\src\ai.rs` (CREATED)
- `C:\Users\lowes\AppData\Local\Programs\Warp\src\config.rs` (MODIFIED)
- `C:\Users\lowes\AppData\Local\Programs\Warp\src\main.rs` (MODIFIED)
- `C:\Users\lowes\AppData\Local\Programs\Warp\src\panels.rs` (MODIFIED)
- `C:\Users\lowes\AppData\Local\Programs\Warp\src\window_mgmt.rs` (MODIFIED)
- `C:\Users\lowes\AppData\Local\Programs\Warp\html\clipboard.html` (REWRITTEN)
- `C:\Users\lowes\AppData\Local\Programs\Warp\html\chat.html` (CREATED)
- `C:\Users\lowes\AppData\Local\Programs\Warp\html\settings.html` (MODIFIED)
- `C:\Users\lowes\Documents\Theophysics Master\safe_edge_tts.py` (CREATED)
- `O:\999_IGNORE\TTS_Engines\Edge TTS\Convert-TTS.bat` (MODIFIED)

### GitHub
- Commit 146286c pushed to YellowKidokc/nerve (pre-custom-protocol changes)
- Custom protocol fix in panels.rs still local only

---

## VALIDATION

- **Assessor:** Claude Opus 4.6
- **Confidence Score:** 82%
- **Weakest Link:** The nerve:// custom protocol fix is the critical unverified piece. If it doesn't resolve the WebView2 JavaScript execution issue, all panel interactivity (settings, clipboard JS, AI tab) remains broken and a different approach will be needed.
- **Status:** DEPLOYED (all features), PENDING VERIFICATION (custom protocol fix)

---

*Theophysics Research Program | POF 2828*
*Template v2.0 | April 2026*
