# Phase 1 Brief — TTS Dual-Hive Fix

**Audience:** an AI coding agent (Codex, Claude Code, Cursor agent, etc.) that has been pointed at this repository and asked to do work.

**Scope:** this brief covers Phase 1 only. Phases 2-4 in README.md are vision documents and are explicitly out of scope. Do not implement them. Do not ask to implement them. If you find yourself thinking about Cloudflare, PWAs, or AI classification dashboards while reading this, stop and reread this paragraph.

---

## What you are fixing

Nerve's TTS Engine currently shows only 3 voices in its dropdown and emits `ERROR: interrupted` when the user tries to speak. The full diagnosis is in `docs/HISTORICAL_FIXES.md` under the 2026-04-08 entry. Read it first.

The short version: two independent bugs are stacked.

1. **SAPI enumeration only reads the legacy registry hive.** OneCore/Neural voices live in a separate hive that the default `SpEnumTokens(SPCAT_VOICES)` call never touches.
2. **Edge TTS subprocess fails silently.** Multiple failure modes (PATH, missing package, network timeout, WOW64) all collapse into the same symptom: empty voice list, no error message.

The `ERROR: interrupted` message is downstream of both — when the voice list is incomplete or stale, `tts_speak` calls `SetVoice()` with a token ID that doesn't exist in the current enumeration, SetVoice fails, the utterance is cancelled, and the handler emits `interrupted` to the status bar.

## What you will deliver

Six concrete changes, all in `src/tts.rs` (and possibly small touches in `src/ipc.rs` to surface new error types). Reference implementations for changes 1-4 are in `docs/REFERENCE_TTS_RS.md` — adapt them into the existing module structure rather than copy-pasting verbatim.

### Change 1: Dual-hive voice enumeration

Replace the existing single-path SAPI enumeration with one that reads both `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices` and `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices` via `ISpObjectTokenCategory::SetId()` with the path string passed directly. There is no `SPCAT_` constant for the OneCore path — pass the literal string.

**Critical:** dedup the merged result by **Name attribute, not token ID**. Microsoft David, Zira, and Mark exist in both hives with different token paths but the same display name. Naive dedup-by-ID would show all three voices twice.

Add a `hive` field to `VoiceInfo` (`"sapi"` or `"onecore"`) so downstream code can normalize volume per-hive.

### Change 2: Edge TTS preflight checks

Before calling `Command::new("py").args(["-m", "edge_tts", "--list-voices"])`, run two probes:

1. `py --version` — confirm the launcher is on PATH and functional
2. `py -c "import edge_tts; print('ok')"` — confirm the package is importable in the resolved Python install

Both probes should produce specific, actionable error messages on failure. Surface these errors to the frontend through the existing IPC error path. The user must be able to see "Python not found on PATH" or "edge-tts package missing" in the UI instead of just an empty dropdown.

### Change 3: Voice list cache fallback

Persist the last successful voice enumeration to `%LOCALAPPDATA%\ClipSync\voice_cache.json`. If a fresh enumeration fails entirely (both SAPI and Edge return errors), load and return the cached list with a flag indicating the result is stale.

Use `serde_json` for the format. The cache file should be valid JSON of `Vec<VoiceInfo>`.

### Change 4: Token ID validation in tts_speak

Before calling `ISpVoice::SetVoice()`, look up the requested voice ID in the current enumeration. If it's not present, return a descriptive error to the frontend (`"voice X is no longer available, please select another"`) instead of letting SetVoice fail silently into the `interrupted` path.

### Change 5: Subprocess timeout

The `py -m edge_tts --list-voices` call should not be allowed to block forever. Add an 8-second timeout. `std::process::Command` has no built-in timeout on Windows — implement it with a thread + channel pattern, or add a single small dependency like `wait-timeout` if the project doesn't already have one. Do not add multiple dependencies just for this.

### Change 6: Volume normalization for OneCore voices

OneCore voices render approximately 10-15% louder than SAPI Desktop voices at the same volume value. In the `tts_speak` handler, if the voice's `hive` field is `"onecore"`, scale the requested volume down by a factor of `0.87` (or expose a per-engine volume offset in config — your call, but document whichever choice you make).

---

## Success criteria

You are done with Phase 1 when **all** of these are true:

1. On a Windows 11 machine with default Neural voices installed, `get_voices` returns at least 19 voices: David, Zira, Mark from SAPI legacy plus Aria, Jenny, Guy, Eric, Christopher, Michelle, Ana, Roger, Steffan, etc. from OneCore Neural, plus all available Edge voices when `py -m edge_tts` is functional.
2. With `py` removed from PATH or `edge-tts` uninstalled, the frontend displays a clear error message identifying the specific failure (not just "no voices").
3. `tts_speak` with a valid voice ID succeeds without producing `ERROR: interrupted`.
4. `tts_speak` with an invalid or stale voice ID returns a descriptive error containing the voice name, not silent interrupt.
5. Disconnecting from the network and restarting Nerve still produces a populated voice list (loaded from cache).
6. No regressions in clipboard polling, link tracking, or any other existing functionality. The only files you should be modifying are `src/tts.rs` and possibly small additions to `src/ipc.rs` and `Cargo.toml`.

## What you must NOT do

- Do not migrate to Tauri or any other framework. Nerve uses raw `webview2-com` + `windows-rs` deliberately.
- Do not refactor `clip.rs`, `links.rs`, `main.rs`, or any HTML files unless strictly required to surface a new error type.
- Do not add dependencies beyond what's needed for changes 1-6. Every dependency added must be justified in the PR description.
- Do not implement Cloudflare sync, PWA support, or AI classification. Those are Phases 2-4 and are not authorized.
- Do not "improve" the error messages by making them friendlier or vaguer. The user wants specific, actionable errors that point at the actual failure.
- Do not delete or rewrite `docs/HISTORICAL_FIXES.md` entries. Add new entries only.

## Deliverables

A single pull request containing:

1. The code changes described above
2. A new entry at the top of `docs/HISTORICAL_FIXES.md` documenting what you changed and how to verify it
3. A short PR description explaining which of the six changes are in the PR (all six should be), any deviations from the reference implementations, and any new dependencies added

If you cannot complete all six changes in one PR, split them by change number (PR for change 1, PR for change 2, etc.) — but keep changes 1, 2, and 4 together since they're tightly coupled.

## Questions

If anything in this brief is ambiguous, prefer the interpretation that does the smallest amount of work and the fewest cross-cutting changes. When in doubt, ask the maintainer in the PR description rather than guessing and refactoring.
