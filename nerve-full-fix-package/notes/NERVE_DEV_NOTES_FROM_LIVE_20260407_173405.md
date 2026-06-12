# Nerve — Developer Notes & Fix Log
**POF 2828 | David Lowe**
Last updated: April 5, 2026

---

## Critical: Two separate file locations

Nerve has **two copies of the HTML files**. Editing the wrong one does nothing.

| Location | Purpose |
|---|---|
| `C:\Users\lowes\Downloads\nerve-main\nerve-main\` | Source code — edit here |
| `C:\Users\lowes\AppData\Local\ClipSync\` | **Live install — what actually runs** |

**After editing any HTML file**, copy it to the live install:
```powershell
$src = "C:\Users\lowes\Downloads\nerve-main\nerve-main\html"
$dst = "C:\Users\lowes\AppData\Local\ClipSync\html"
Copy-Item "$src\settings.html" "$dst\settings.html" -Force
Copy-Item "$src\clipboard.html" "$dst\clipboard.html" -Force
Copy-Item "$src\links.html" "$dst\links.html" -Force
```

**After editing any Rust file** (`src\*.rs`), rebuild and deploy:
```batch
# Run this — it's at the project root:
C:\Users\lowes\Downloads\nerve-main\nerve-main\build.bat

# Then copy the new binary:
copy "C:\Users\lowes\Downloads\nerve-main\nerve-main\target\release\nerve.exe" ^
     "C:\Users\lowes\AppData\Local\ClipSync\nerve.exe"
```

---

## Restart procedure (clears WebView2 cache)

WebView2 aggressively caches HTML. If your HTML changes aren't showing up:

```powershell
# Kill nerve, clear cache, restart
Stop-Process -Name "nerve" -Force -ErrorAction SilentlyContinue
Start-Sleep 1
Remove-Item "C:\Users\lowes\AppData\Local\ClipSync\nerve.exe.WebView2" -Recurse -Force -ErrorAction SilentlyContinue
Start-Process "C:\Users\lowes\AppData\Local\ClipSync\nerve.exe"
```

---

## Build script

`build.bat` at project root:
```batch
@echo off
cd /d "C:\Users\lowes\Downloads\nerve-main\nerve-main"
"C:\Program Files\Rust stable MSVC 1.93\bin\cargo.exe" build --release
echo BUILD EXIT CODE: %ERRORLEVEL%
pause
```

Rust is at `C:\Program Files\Rust stable MSVC 1.93\bin\cargo.exe` — not in PATH by default.
Build takes 1-3 minutes. EXIT CODE 0 = success.

---

## Fix: Edge TTS voices not showing

**Symptom:** Settings → TTS → Engine: Edge → click 🔄 refresh → no voices appear, or only fallback voices (GuyNeural, JennyNeural).

**Root cause:** `tts.rs` called `python` to run `edge_tts --list-voices`, but this machine uses `py.exe` (Windows Python Launcher), not `python`.

**Fix applied (April 5, 2026):** `list_edge_voices()` in `tts.rs` now tries `py`, `python`, `python3` in order. Same fix applied to `speak_edge_tts()`.

**Verify edge-tts is installed:**
```cmd
py -m edge_tts --list-voices
```
Should output 300+ voices. If it says "No module named edge_tts":
```cmd
py -m pip install edge-tts
```

**Default voice:** `en-US-BrianMultilingualNeural` — best quality English male voice.

---

## Fix: TTS speak button not working (WebView2)

**Symptom:** SPEAK / PAUSE / STOP buttons in `tts-engine.html` do nothing or throw `doSpeak is not defined`.

**Root cause:** The standalone `tts-engine.html` used the browser's `speechSynthesis` Web Speech API, which silently fails inside WebView2. WebView2 blocks audio context until a user gesture unlocks it, and `onvoiceschanged` is unreliable.

**Fix applied (April 5, 2026):** TTS functionality moved into **Settings → TTS tab**. The SPEAK section there sends an IPC message (`tts_speak`) to the Rust backend, which calls Windows SAPI or Edge TTS natively — same path as TEST VOICE which always worked.

`tts-engine.html` is now retired as a standalone panel. Don't try to fix it — the Settings TTS tab is the replacement.

**The IPC path that works:**
```
Settings HTML → sendIpc({ type: 'tts_speak', text: '...' })
  → main.rs handle_ipc() → tts::speak()
    → Windows SAPI (powershell) OR edge-tts (py -m edge_tts)
```

---

## Fix: tts_speak IPC handler

**If SPEAK button shows "NO AGENT" toast**, the compiled binary predates the `tts_speak` handler. Rebuild.

Handler in `main.rs` (inside `handle_ipc` match block):
```rust
"tts_speak" => {
    if let Some(text) = msg.get("text").and_then(|v| v.as_str()) {
        let text = text.to_string();
        std::thread::spawn(move || {
            tts::speak(&text);
        });
    }
}
```

---

## Fix: HTML changes not appearing after edit

1. Did you edit the file in Downloads? → Copy to AppData (see top)
2. Is WebView2 caching the old version? → Clear cache and restart (see restart procedure)
3. Is Nerve running the old binary? → Check binary timestamp: `Get-Item "C:\Users\lowes\AppData\Local\ClipSync\nerve.exe" | Select-Object LastWriteTime`

---

## Hotkeys (default)

| Hotkey | Action |
|---|---|
| Ctrl+Alt+C | Toggle clipboard panel |
| Ctrl+Alt+P | Toggle prompts panel |
| Ctrl+Alt+L | Toggle links panel |
| Ctrl+Alt+R | Toggle research panel |
| Ctrl+Alt+A | Toggle AI chat |
| Ctrl+Alt+T | Read selected text aloud |
| Ctrl+Alt+G | Toggle dashboard |
| Ctrl+Alt+S | Toggle settings |
| Ctrl+Space | AI rewrite selected text |
| Ctrl+Shift+1-10 | Paste clipboard slots 1-10 |

Config saved at: `C:\Users\lowes\AppData\Roaming\clipsync-agent\config.json`

---

## Panel definitions

Panels defined in `src\config.rs` → `default_panels()`. Each has name, title, URL, width, height, always_on_top.

| Panel name | File | Hotkey |
|---|---|---|
| clipboard | clipboard.html | Ctrl+Alt+C |
| prompts | prompt_picker.html | Ctrl+Alt+P |
| links | links.html | Ctrl+Alt+L |
| research | research.html | Ctrl+Alt+R |
| chat | chat.html | Ctrl+Alt+A |
| dashboard | dashboard.html | Ctrl+Alt+G |
| settings | settings.html | Ctrl+Alt+S |
| tts | tts-engine.html | (retired — use settings) |

---

## Startup: all panels open on launch

`main.rs` → `Event::NewEvents(StartCause::Init)` opens all panels sequentially with 300ms stagger so they pop up one by one. Close the ones you don't want — hotkeys bring them back.

---

## Architecture summary

```
nerve.exe (Rust/WebView2)
├── src/main.rs          — event loop, IPC handler, hotkey routing
├── src/config.rs        — panel defs, hotkey defaults, config load/save
├── src/panels.rs        — WebView2 window creation and management
├── src/tts.rs           — Windows SAPI + Edge TTS speak/stop/list
├── src/hotkeys.rs       — global hotkey registration
├── src/hotstrings.rs    — low-level keyboard hook for /trigger expansion
├── src/clipboard.rs     — clipboard monitor + slot management
├── src/ai.rs            — Claude/OpenAI/local LLM API calls
└── html/                — all UI (served via nerve:// custom protocol)
    ├── settings.html    — main settings + TTS speak interface
    ├── clipboard.html   — clipboard slots + history
    ├── links.html       — link library with two-column cards
    └── ...
```

IPC flow: `HTML → window.chrome.webview.postMessage(JSON) → main.rs handle_ipc() → action`
