# Contributing to Nerve

Most contributions to this repository will come from AI coding agents working from a brief. This document is the rules of engagement.

## For AI agents

1. **Read `README.md` first.** It tells you which phase is currently authorized.
2. **Read `docs/HISTORICAL_FIXES.md` before opening any issue or making any change.** Most "new" bugs in this codebase have been seen before.
3. **Read the phase brief in `docs/` that matches the work you're doing.** Currently only `PHASE_1_BRIEF.md` exists. If a brief for the work you've been asked to do does not exist, stop and ask the maintainer to write one. Do not improvise scope.
4. **Stay inside scope.** If the brief says "Phase 1 only," do not touch Phase 2 code. If it says "only `tts.rs`," do not refactor `main.rs` while you're in there.
5. **Document what you did.** Add an entry to `docs/HISTORICAL_FIXES.md` for any non-trivial change. Use the format documented at the bottom of that file.
6. **Prefer small diffs.** A 50-line PR that fixes the bug is better than a 500-line PR that fixes the bug and "cleans up" three other files.
7. **Justify every new dependency.** Adding to `Cargo.toml` is a permanent decision. If you can do the same thing with `std` or with an existing dependency, do that instead. If you do add a dependency, name it and explain why in the PR description.
8. **Do not migrate frameworks.** Nerve uses `webview2-com` + `windows-rs` deliberately. Do not propose moving to Tauri, Electron, Wails, or anything else without explicit maintainer approval.
9. **Do not delete historical fix entries.** Add new ones. The log is append-only.
10. **Surface uncertainty in the PR description.** If you made a judgment call, say so. If you weren't sure whether to do X or Y, say so. The maintainer can tell you which way to go faster than they can untangle a wrong choice.

## For human contributors

Same rules apply, with one addition: if you're a human and you find yourself doing the kind of "let me clean up this file while I'm in here" pass that AI agents are forbidden from doing, stop and open a separate PR for it. Mixed-purpose PRs are hard to review and harder to revert.

## What a good PR looks like

- Title names the phase and the change ("Phase 1 / Change 1: dual-hive voice enumeration")
- Description lists each success criterion from the brief and how this PR addresses it
- Diff is scoped to the files named in the brief
- New entry in `docs/HISTORICAL_FIXES.md`
- No new dependencies, or new dependencies justified inline
- Builds with `build.bat` and exits with code 0

## What gets a PR rejected

- Out-of-scope changes (touching files the brief didn't authorize)
- Framework migrations
- Adding dependencies without justification
- Deleting or rewriting historical fix entries
- Suppressing errors instead of surfacing them
- "Improving" code style in ways that aren't asked for
- PRs that build but don't actually run on a real Windows machine

## Testing

There is currently no automated test suite. This is a known gap. For Phase 1, manual verification against the success criteria in `docs/PHASE_1_BRIEF.md` is the bar. A future phase will likely add a test harness, but that is its own scoped project and not something to add ad-hoc inside another PR.

## Reporting bugs

Open a GitHub issue with:
- Symptom (what you saw)
- Expected (what you expected)
- Repro steps (numbered list, exact commands)
- Environment (Windows version, Nerve version/commit, Python version if relevant)

If the bug looks similar to anything in `docs/HISTORICAL_FIXES.md`, link the relevant entry. If it's identical, the fix may already be in main and you may just need to update.
