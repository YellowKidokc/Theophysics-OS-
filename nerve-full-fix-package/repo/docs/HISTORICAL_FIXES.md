# Historical Fix Log

Bugs fixed in earlier sessions. Read this before opening any issue or making any change — most "new" bugs in this codebase have been seen and fixed before, and the fix patterns are documented here.

---

## 2026-04-08 — Phase 1 TTS dual-hive fix (all 6 changes)

**Symptom:** TTS Engine dropdown showed only 3 legacy SAPI voices (David, Zira, Mark). Selecting any voice produced `ERROR: interrupted`. Edge TTS voices never appeared.

**Root cause:** Two stacked bugs — (1) voice enumeration only read the legacy SAPI registry hive, missing all OneCore/Neural voices, and (2) Edge TTS subprocess failed silently with no actionable error surfaced to the user. The `interrupted` error was downstream: `speak()` attempted to use a voice name that didn't resolve to a valid token, causing the utterance to cancel.

**Fix — 6 changes in `src/tts.rs` + `Cargo.toml`:**

1. **Dual-hive voice enumeration (Change 1):** Replaced PowerShell-based `System.Speech.GetInstalledVoices()` with direct COM enumeration via `ISpObjectTokenCategory::SetId()` reading both `HKLM\...\Speech\Voices` and `HKLM\...\Speech_OneCore\Voices`. Deduplicates by display name (not token ID) since David/Zira/Mark exist in both hives. Added `VoiceInfo` struct with `id`, `name`, `lang`, `hive` fields.

2. **Edge TTS preflight checks (Change 2):** Before spawning `py -m edge_tts --list-voices`, probes `py --version` and `py -c "import edge_tts"` with specific, actionable error messages on each failure mode (Python not on PATH, package missing, package broken).

3. **Voice list cache fallback (Change 3):** Persists last successful enumeration to `%LOCALAPPDATA%\ClipSync\voice_cache.json`. If fresh enumeration fails entirely, loads and returns cached list with `stale: true` flag.

4. **Token ID validation in speak (Change 4):** Before speaking, validates the configured voice name against the in-memory or file-cached voice list. Returns descriptive error `"Voice 'X' is no longer available"` instead of silent `interrupted` failure. Gracefully skips validation if voice list hasn't been populated yet.

5. **8-second subprocess timeout (Change 5):** `edge_tts --list-voices` now has an 8-second timeout using a `try_wait` poll loop (no external dependency). Timeout produces specific error mentioning `speech.platform.bing.com`.

6. **OneCore volume normalization (Change 6):** OneCore voices are ~10-15% louder than SAPI Desktop at the same volume value. When speaking a OneCore voice, volume is scaled by `0.87` factor. Configurable via `ONECORE_VOLUME_FACTOR` constant.

**Additional changes:**
- `speak_sapi()` now uses `SAPI.SpVoice` COM object (not `System.Speech.SpeechSynthesizer`) so OneCore voice tokens can be set via `ISpeechObjectToken::SetId()` in PowerShell.
- Speaking subprocess PID is tracked for reliable `stop()` via `taskkill /PID`.
- Added `Win32_System_Com` feature to `Cargo.toml` for `CoCreateInstance`/`CoInitializeEx`.
- `speak()` now returns `Result<(), String>` to surface voice validation errors.
- Backward-compatible `list_voices()` wrapper preserved for existing callers.

**How to verify:** On Windows 11, call `get_voices()` — should return 19+ voices (3 legacy SAPI + OneCore Neural + Edge voices when py/edge-tts available). Remove `py` from PATH → Edge error message appears. Use invalid voice name → descriptive error returned. Delete `voice_cache.json`, disconnect network, restart → cache fallback activates.

---

## 2026-04-08 — TTS Engine showing 3 voices + ERROR: interrupted

**Symptom:** TTS Engine standalone window shows only 3 voices (Microsoft David, Zira, Mark). "Reload Voices" button does nothing. Status bar reads `ERROR: interrupted` on speak attempts.

**Root cause #1:** SAPI's `SpEnumTokens(SPCAT_VOICES)` only reads `HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens`. Modern OneCore/Neural voices live in `HKLM\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens` — a separate registry hive the default enumerator never touches.

**Root cause #2:** `py -m edge_tts --list-voices` was failing silently. Possible reasons: `py` not on PATH in tray-launched env, `edge-tts` package missing, network timeout to `speech.platform.bing.com`, WOW64 redirect.

**Downstream effect (the "interrupted" error):** when both enumeration paths return empty/short lists, the HTML dropdown is populated from a stale previous call. `tts_speak` then calls `ISpVoice::SetVoice()` with a token ID that no longer exists, SetVoice fails, the utterance is cancelled mid-stream, and the handler emits `"interrupted"` to the status bar.

**Fix:** dual-hive enumeration (read both SAPI and OneCore paths via `ISpObjectTokenCategory::SetId()` with the path string, not the SPCAT constant) + Edge preflight checks (probe `py --version` and `import edge_tts` before subprocess spawn) + voice list cache fallback + token ID validation in `tts_speak`. Reference implementation in `docs/REFERENCE_TTS_RS.md`.

**Critical detail:** dedup the merged voice list **by Name attribute, not token ID**. David/Zira/Mark exist in both hives with different token paths but the same display name — naive dedup-by-ID would show all three voices twice.

**Workaround for users on older binaries:** run as Administrator:
```powershell
reg copy "HKLM\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens" `
         "HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens" /s /f
```
This copies OneCore tokens into the legacy hive so the existing single-path enumerator finds them. Not a permanent fix — Windows Update can wipe the merge.

---

## 2026-04-05 — Edge voices not appearing in TTS tab

**Symptom:** TTS settings tab only showed SAPI voices, no Edge neural voices.

**Root cause:** Rust was calling `Command::new("python")` but the Windows Python launcher binary is `py.exe`, not `python.exe`. The subprocess spawn failed with file-not-found, the error was swallowed, and the voice list silently fell back to SAPI-only.

**Fix:** `tts.rs` now tries `py`, `python`, `python3` in order. Default Edge voice changed from `en-US-GuyNeural` to `en-US-BrianMultilingualNeural`.

**Why this fix was incomplete:** it solved the binary lookup but didn't address the OneCore SAPI hive split (the bigger Root Cause #1 above) or the other subprocess failure modes (network timeout, package missing, WOW64). Those were caught in the 2026-04-08 session.

---

## 2026-04-04 — HTML edits not appearing in app

**Symptom:** Edits to `settings.html` (or any HTML file) didn't show up after restarting Nerve, even after multiple restarts and cache clears.

**Root cause:** Nerve has **two copies** of the HTML files. The development source lives in `<repo>/html/`, but the live install runs from `%LOCALAPPDATA%\ClipSync\html\`. All edits were going to the source, the running app was reading from the live install, the two were never connected.

**Fix:** after editing any HTML file in the repo, copy it to the live install:
```powershell
copy "<repo>\html\*.html" "$env:LOCALAPPDATA\ClipSync\html\"
```

The same gotcha applies to `nerve.exe` itself — `cargo build --release` outputs to `target/release/nerve.exe` but the running binary is `%LOCALAPPDATA%\ClipSync\nerve.exe`. The build does not deploy.

**Long-term fix candidate:** add a `cargo xtask deploy` step or a `build.bat` that does build + copy in one shot. Currently `build.bat` only does the build.

---

## 2026-04-04 — nerve.exe locked, can't redeploy

**Symptom:** `Copy-Item` to `%LOCALAPPDATA%\ClipSync\nerve.exe` fails with "the file is being used by another process" even after `Stop-Process -Name nerve`.

**Root cause:** WebView2 spawns child processes (one per WebView2 control) that hold handles to the parent `nerve.exe`. `Stop-Process -Name nerve` only kills the parent process — the children survive briefly and continue holding the file lock.

**Fix:** kill the entire process tree:
```powershell
taskkill /F /T /IM nerve.exe
```
The `/T` flag terminates the named process and all child processes. After this, the file lock releases and `Copy-Item` succeeds.

**Alternative:** use Task Manager → right-click `nerve` → "End task" (which kills the tree) instead of "End process" (which kills only the parent).

---

## Format for future entries

When adding new entries to this log, follow this structure:

```markdown
## YYYY-MM-DD — Short symptom description

**Symptom:** What the user saw or what was broken.

**Root cause:** The actual underlying mechanism. Be specific. "It was a bug" is not a root cause.

**Fix:** What changed in the code or environment. Include file names and function names where relevant.

**Why it matters:** Optional. If the fix has implications for other parts of the codebase, note them here.
```

This format makes the log searchable and gives future debuggers (human or AI) enough context to recognize a recurrence of the same problem.
