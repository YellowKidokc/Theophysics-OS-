# Nerve

**Clipboard manager + TTS engine + link tracker for Windows.**
Rust binary with a WebView2 frontend, dual TTS engines (SAPI + Edge Neural), and a sync layer that talks to Cloudflare for cross-device continuity.

> **Status:** Active development, ~18 months in. Currently in transition from local-only to Cloudflare-synced architecture. **Phase 1 of the GitHub rebuild is the only work currently scoped for an AI coding agent.** Phases 2-4 are vision documents, not work orders.

---

## What Nerve does

- **Clipboard capture and history.** Polls the Windows clipboard, stores everything (text, images, files), exposes a searchable history panel.
- **TTS engine.** Speaks any clipboard content or arbitrary text through one of two engines:
  - **SAPI5** (Windows native, fast, offline)
  - **Edge Neural Voices** (~300 voices, network-fetched, much higher quality)
- **Link tracker.** Captures URLs from clipboard, deduplicates, organizes into a links panel.
- **Auto-speak mode.** Toggle in the clipboard panel — any new Ctrl+C content speaks automatically through the selected voice.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  WebView2 frontend (HTML/JS)                                │
│  ├── settings.html       — TTS configuration tab            │
│  ├── clipboard.html      — clipboard history + auto-speak   │
│  ├── tts-engine.html     — standalone TTS Engine window     │
│  └── links.html          — link tracker                     │
└─────────────────────────┬──────────────────────────────────┘
                          │ IPC (sendIpc → window.chrome.webview)
┌─────────────────────────▼──────────────────────────────────┐
│  Rust binary (nerve.exe)                                    │
│  ├── main.rs   — window mgmt, IPC dispatcher                │
│  ├── tts.rs    — voice enumeration, speak/stop/download     │
│  ├── clip.rs   — clipboard polling                          │
│  └── ipc.rs    — handler registry                           │
└─────────────────────────┬──────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   ┌────────────────┐         ┌──────────────────────┐
   │  SAPI5 COM     │         │  py -m edge_tts      │
   │  (legacy +     │         │  (~300 neural voices)│
   │  OneCore hives)│         │  network fetch       │
   └────────────────┘         └──────────────────────┘
```

**Critical architectural fact:** the HTML/JS layer **never** calls `window.speechSynthesis`. All TTS goes through Rust IPC handlers. Browser-style fixes (`onvoiceschanged`, `getVoices`, Web Speech API) do not apply to this stack — they target the wrong layer.

---

## Phase 1 — Land the TTS fixes (SCOPED, ready for an AI coding agent)

This is the only work currently authorized for Codex/Claude Code/etc. Everything below this section is vision, not work.

### The bug being fixed

The TTS Engine window currently shows only 3 voices and emits `ERROR: interrupted` on speak attempts. Two independent root causes are stacked:

**Root Cause 1 — SAPI only enumerates the legacy registry hive.**
`SpEnumTokens(SPCAT_VOICES)` exclusively reads `HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens`. Modern OneCore/Neural voices live in `HKLM\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens` — a separate hive the default enumerator never touches. Result: only 3 legacy Desktop voices visible.

**Root Cause 2 — Edge TTS subprocess fails silently.**
`py -m edge_tts --list-voices` can fail because:
1. `py` not on PATH in the env Rust inherits from tray/autostart
2. `edge-tts` package missing in the resolved Python install
3. Network timeout — `--list-voices` does a live fetch to `speech.platform.bing.com`
4. WOW64 redirect if the Rust binary is 32-bit and Python is 64-bit

**Downstream symptom — `ERROR: interrupted`.** When enumeration returns a short/empty list, the HTML dropdown is populated from a stale previous call. `tts_speak` then calls `ISpVoice::SetVoice()` with a token ID that no longer exists in the current enumeration, SetVoice fails, the utterance is cancelled mid-stream, and the handler emits `"interrupted"` to the status bar.

### Phase 1 deliverables (in order)

1. **Replace `tts.rs` voice enumeration** with a dual-hive enumerator that reads BOTH `Speech\Voices` and `Speech_OneCore\Voices` paths via `ISpObjectTokenCategory::SetId()`. **Dedup by Name attribute, NOT token ID** — Microsoft David, Zira, and Mark exist in both hives with different token paths but the same display name. Reference implementation in `docs/REFERENCE_TTS_RS.md`.

2. **Add Edge TTS preflight checks** before spawning `--list-voices`: probe `py --version`, then probe `py -c "import edge_tts; print('ok')"`, surface clear error messages to the frontend instead of failing silently. Reference implementation in `docs/REFERENCE_TTS_RS.md`.

3. **Add a fallback voice list cache.** If Edge enumeration fails, return the last-known-good list from cache instead of an empty stub. Persist the cache to `%LOCALAPPDATA%\ClipSync\voice_cache.json`.

4. **Validate voice token IDs on `tts_speak`.** Before calling `ISpVoice::SetVoice()`, check the requested token ID exists in the current enumeration. If not, return a descriptive error to the frontend (`"voice X no longer available, please reselect"`) instead of triggering the silent interrupt path.

5. **Add an 8-second subprocess timeout** to the `--list-voices` call so a network hang doesn't block the `get_voices` IPC response indefinitely.

6. **Volume normalization for OneCore voices.** OneCore voices render ~10-15% louder than SAPI5 Desktop voices at the same volume value. In the `tts_speak` handler, scale the volume parameter down for tokens whose `hive` field is `"onecore"`. Or expose per-engine volume in the UI — agent's choice.

### Phase 1 success criteria

- `get_voices` IPC returns ≥19 voices on a Windows 11 machine with default Neural voices installed (David, Zira, Mark from SAPI; Aria, Jenny, Guy, Eric, Christopher, Michelle, Ana, Roger, Steffan from OneCore Neural; plus all Edge voices if `py -m edge_tts` works on the test machine).
- Edge TTS failures produce a visible error in the frontend, not silent fallback.
- `tts_speak` with a valid token ID succeeds without `ERROR: interrupted`.
- `tts_speak` with an invalid token ID returns a descriptive error, not silent interrupt.
- Voice list survives a network outage (cached fallback works).

### What Phase 1 explicitly does NOT include

- Cloudflare sync (Phase 2)
- PWA (Phase 3)
- Dashboard / classification (Phase 4)
- Any new UI features beyond what's needed to surface the new error states
- Any refactoring of `clip.rs` or `links.rs` — leave them alone
- Migration to `tauri` or any framework rewrite — Nerve stays raw `webview2-com` + `windows-rs`

---

## Phase 2 — Cloudflare sync layer (NOT YET SCOPED, vision only)

Future work. Do not implement until Phase 1 ships and stabilizes.

**Goal:** Nerve becomes one of N clients sharing a single user's clipboard, audio, and link state across devices via Cloudflare infrastructure.

**Target architecture:**
- **Cloudflare D1** — SQLite-compatible database holding clipboard metadata, voice cache, link records, classification tags
- **Cloudflare R2** — bucket storage for clipboard binary content, audio files, images, video, documents
- **Cloudflare Workers** — REST API endpoints the desktop app and PWA both call
- **Cloudflare Pages** — PWA hosting (installable on desktop and mobile)
- **Domain:** `clipsync.faiththruphysics.com` or similar subdomain of an existing controlled domain
- **Auth:** Cloudflare Access or a long-lived token David controls; no third-party identity provider

**Sync model:** every clipboard event from Nerve POSTs to a Worker → Worker writes metadata to D1 and binary content to R2 → other clients poll (or subscribe via Durable Objects + WebSockets) for changes. Last-write-wins for the first cut; CRDTs only if conflicts become a real problem.

**Existing infrastructure to align with:** the user already operates `comms.faiththruphysics.com` as a Cloudflare Worker + D1 setup. New ClipSync API should follow the same patterns and conventions. Read the comms hub source before designing the new API surface.

---

## Phase 3 — PWA (NOT YET SCOPED, vision only)

Cloudflare Pages-hosted Progressive Web App that the user installs on desktop and phone. Renders the same clipboard / TTS / links views as the Rust desktop app, but pulls all state from the Cloudflare API instead of from local Rust IPC.

**Key design constraint:** the PWA cannot speak through SAPI or OneCore voices — it has only the browser's `window.speechSynthesis` API. This is the one place where the wrong-layer fix from Phase 1 actually applies. Voice selection in the PWA pulls from `speechSynthesis.getVoices()` and runs entirely in the browser.

The PWA displays the SAPI/Edge voice list from the desktop app for reference, but cannot use those voices itself.

---

## Phase 4 — AI classification dashboard (NOT YET SCOPED, vision only)

A separate Cloudflare Pages site that reads from the same D1 + R2 backing store and runs AI classification over clipboard content. Sorts, tags, and organizes by topic, project, source application, time of day, etc. Likely uses Workers AI or an external LLM API for the classification step.

This is the layer where "AI organizes my thoughts" lives. Do not start until Phases 1-3 are stable.

---

## Build instructions

### Prerequisites

- Windows 10 1703+ or Windows 11
- Rust toolchain (stable MSVC) — currently at `C:\Program Files\Rust stable MSVC 1.93\bin\cargo.exe` on the dev machine, not in PATH by default
- WebView2 runtime (preinstalled on Windows 11)
- Python 3.10+ with `edge-tts` installed (`py -m pip install edge-tts`) for Edge voice support
- Optional: Visual Studio Build Tools for the C++ linker

### Build

```batch
build.bat
```

This runs `cargo build --release` with the right cargo path. Build time: 1-3 minutes. Exit code 0 = success. Output: `target\release\nerve.exe`.

### Deploy to live install

Nerve installs to `%LOCALAPPDATA%\ClipSync\`. After building:

```powershell
# Kill running instance (use process tree kill — WebView2 holds handles)
taskkill /F /T /IM nerve.exe

# Copy new binary
copy "target\release\nerve.exe" "$env:LOCALAPPDATA\ClipSync\nerve.exe"

# Copy HTML changes if any
copy "html\*.html" "$env:LOCALAPPDATA\ClipSync\html\"

# Clear WebView2 cache (it caches HTML aggressively)
Remove-Item "$env:LOCALAPPDATA\ClipSync\nerve.exe.WebView2" -Recurse -Force -ErrorAction SilentlyContinue

# Restart
Start-Process "$env:LOCALAPPDATA\ClipSync\nerve.exe"
```

### Two-location gotcha

Nerve has **two copies** of the HTML files during development:
- `<repo>/html/` — source, edit here
- `%LOCALAPPDATA%\ClipSync\html\` — live install, what actually runs

After editing any HTML file you must copy it to the live install or your changes won't appear.

---

## Repository layout

```
nerve/
├── src/
│   ├── main.rs              — entry point, window mgmt, IPC dispatcher
│   ├── tts.rs               — voice enumeration, speak/stop/download
│   ├── clip.rs              — clipboard polling
│   └── ipc.rs               — handler registry
├── html/
│   ├── settings.html
│   ├── clipboard.html
│   ├── tts-engine.html
│   └── links.html
├── docs/
│   ├── REFERENCE_TTS_RS.md  — reference implementations for Phase 1 fixes
│   ├── ARCHITECTURE.md      — extended architecture notes
│   └── HISTORICAL_FIXES.md  — log of bugs fixed in earlier sessions
├── Cargo.toml
├── build.bat
├── README.md                — this file
└── .gitignore
```

---

## Historical fix log (do not regress)

**2026-04-05 — Edge voices not appearing.** Rust was calling `python` instead of `py.exe`. Fixed by trying `py`, `python`, `python3` in order. Also changed Edge default to `en-US-BrianMultilingualNeural`.

**2026-04-04 — HTML edits not appearing.** Two-location gotcha — source vs live install. Always copy HTML to `%LOCALAPPDATA%\ClipSync\html\` after editing.

**2026-04-04 — `nerve.exe` locked, can't redeploy.** WebView2 child processes hold handles to the parent exe. Use `taskkill /F /T /IM nerve.exe` (the `/T` flag kills the entire process tree, not just the parent).

---

## License

TBD. Currently private to the author.

## Author

David Lowe (POF 2828) — built across ~18 months of intensive development with multiple AI collaborators.
