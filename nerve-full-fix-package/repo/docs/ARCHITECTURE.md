# Nerve Architecture

Extended notes on how Nerve is structured. For the high-level summary, see README.md.

## Layer model

Nerve is a three-layer Windows desktop application:

1. **Native shell** — a Rust binary (`nerve.exe`) that owns the OS-level resources: clipboard polling, COM bindings to SAPI, subprocess management for Edge TTS, file system, and the WebView2 host window.
2. **WebView2 frontend** — HTML/JS pages rendered inside an embedded Microsoft Edge WebView2 control. This is the UI layer. It is **not** a browser tab — it has no Web Speech API access in the way a real browser does, and it talks to the native shell through a custom IPC channel.
3. **External engines** — SAPI5 (in-process COM) and Edge TTS (out-of-process Python subprocess). Both are owned by the Rust shell, never touched directly by the WebView2 frontend.

## IPC contract

The frontend talks to the shell through `window.chrome.webview.postMessage()` with a typed envelope:

```javascript
sendIpc({ type: 'tts_speak', voice: 'en-US-Aria', text: 'hello' })
```

The Rust side has a dispatcher in `ipc.rs` that routes by the `type` field to handlers. Current handler list:

| Type | Direction | Purpose |
|---|---|---|
| `get_voices` | frontend → Rust | Return enumerated voice list |
| `tts_speak` | frontend → Rust | Speak text with given voice |
| `tts_stop` | frontend → Rust | Cancel current utterance |
| `tts_download` | frontend → Rust | Save text-to-speech as WAV to Desktop |
| `get_clips` | frontend → Rust | Return clipboard history |
| `clip_added` | Rust → frontend | Push notification when clipboard captures something new |

All payloads are JSON. There is no schema enforcement yet — adding `serde`-validated structs would be a useful Phase 1.5 hardening pass.

## TTS engine selection

Nerve supports two engines, selectable per-utterance:

**SAPI5** — Windows native, in-process COM via `windows-rs` ISpVoice bindings. Synchronous, offline, low latency. Voice list comes from registry enumeration of two separate hives (see REFERENCE_TTS_RS.md). Quality varies — legacy Desktop voices are robotic, OneCore Neural voices are quite good.

**Edge TTS** — out-of-process Python subprocess (`py -m edge_tts`). Asynchronous, requires network, ~300 voices including very high quality multilingual neural voices. Failure modes are documented in REFERENCE_TTS_RS.md.

Engine selection is part of the voice ID — the `hive` field on `VoiceInfo` carries `"sapi"`, `"onecore"`, or `"edge"` so the dispatcher knows which path to take.

## File locations

| Path | Contents |
|---|---|
| `%LOCALAPPDATA%\ClipSync\nerve.exe` | The live binary |
| `%LOCALAPPDATA%\ClipSync\html\` | The live HTML files |
| `%LOCALAPPDATA%\ClipSync\nerve.exe.WebView2\` | WebView2 cache (delete to force HTML reload) |
| `%LOCALAPPDATA%\ClipSync\config.json` | User config (selected voice, engine, etc.) |
| `%LOCALAPPDATA%\ClipSync\voice_cache.json` | Last known good voice list (Phase 1 deliverable #3) |
| `%LOCALAPPDATA%\ClipSync\clips.db` | Clipboard history (SQLite) |

## Build artifacts

`cargo build --release` outputs to `target/release/nerve.exe`. Deploying to the live install requires copying this file to `%LOCALAPPDATA%\ClipSync\nerve.exe`. The binary cannot be replaced while Nerve is running because WebView2 child processes hold handles to the parent — kill the entire process tree first with `taskkill /F /T /IM nerve.exe`.

## Why WebView2 and not Tauri or Electron

Tauri was evaluated and rejected because Nerve started before Tauri 1.0 was stable and the migration cost has never been justified. Electron was rejected because it ships an entire Chromium runtime per app (~200MB) and Nerve targets a tray-resident workflow where memory matters. Raw `webview2-com` + `windows-rs` is the smallest possible footprint that gets a real HTML UI running on Windows.

The cost of this choice: there is no framework. Every IPC handler, window event, and subprocess wrapper is hand-written. The benefit: there is no framework. Nothing in the dependency tree breaks across major version bumps the way Electron does.

## Sync layer (future)

Phases 2-4 in README.md describe a Cloudflare-backed sync layer that does not exist yet. When it ships, Nerve will become one of N clients sharing state through:

- Cloudflare D1 (clipboard metadata, voice cache, link records)
- Cloudflare R2 (binary content, audio, images)
- Cloudflare Workers (REST API)
- Cloudflare Pages (PWA)

The IPC layer described above will gain a `sync_*` handler family that the frontend can call to push/pull state. The Rust side will run a background sync task that batches local changes and reconciles with the Cloudflare API. None of this is built yet. Do not let the existence of this section in the doc create the impression that any of it exists in code.
