# START HERE

This folder is the complete drop-in package for the canonical `YellowKidokc/nerve` GitHub repo. Everything Claude prepared for the Phase 1 TTS fix is already in here in the right place. The only thing you need to do is run one script to merge in your local Rust source, then push.

## What's in this folder

```
nerve-github-dropin/
├── README.md                        ← main repo README, phased
├── CONTRIBUTING.md                  ← rules for AI agents
├── .gitignore                       ← Rust + WebView2 + runtime state
├── package-for-github.ps1           ← the script you run
├── docs/
│   ├── PHASE_1_BRIEF.md             ← exact prompt for Codex
│   ├── REFERENCE_TTS_RS.md          ← working Rust code for the fix
│   ├── ARCHITECTURE.md              ← extended architecture notes
│   └── HISTORICAL_FIXES.md          ← log of past bugs
├── src/                             ← (empty — script populates from your local source)
└── html/                            ← (empty — script populates from your local source)
```

## What's NOT in this folder (and why)

The actual `tts.rs`, `main.rs`, `clip.rs`, `ipc.rs`, `Cargo.toml`, `build.bat`, and `*.html` files are not in this package because they live on your machine in `C:\Users\lowes\Downloads\nerve-main\nerve-main\`. Claude can't see your source files directly, so the script has to merge them in locally on your machine.

If your source is in a different location, edit the `$src` variable at the top of `package-for-github.ps1` before running it.

## How to use this

### 1. Put this folder somewhere you'll find it

A good location: `C:\Users\lowes\Downloads\nerve-github-dropin`

The script defaults to looking there. If you put it somewhere else, edit the `$dropin` variable at the top of `package-for-github.ps1`.

### 2. Run the package script

Open PowerShell, then:

```powershell
cd C:\Users\lowes\Downloads\nerve-github-dropin
.\package-for-github.ps1
```

The script will:
- Copy your `*.rs` files from `nerve-main\src\` into this folder's `src\`
- Copy your `*.html` files from `nerve-main\html\` into this folder's `html\`
- Copy `Cargo.toml` and `build.bat`
- Verify nothing is missing
- Print the exact git commands to push to `YellowKidokc/nerve`

If you see warnings about missing files, read them — they probably mean your local source layout is different from what the script expects, and you'll need to either move files or edit the script.

### 3. Run the git commands

The script prints them at the end. Copy-paste them in order:

```powershell
cd C:\Users\lowes\Downloads\nerve-github-dropin
git init
git add .
git commit -m "Initial canonical package: Phase 1 TTS dual-hive fix scoped"
git branch -M main
git remote add origin https://github.com/YellowKidokc/nerve.git
git push -u origin main --force
```

The `--force` on the first push is intentional. It overwrites whatever empty starter content is in the GitHub repo with this canonical version.

### 4. Archive nerve-1

Go to `https://github.com/YellowKidokc/nerve-1` → Settings → scroll to the bottom → "Archive this repository." This makes it read-only and adds an "Archived" banner so you (and any AI you point at it later) can't accidentally fork off the wrong repo.

### 5. Point Codex at the canonical repo

When you're ready for Codex (or Claude Code, or any coding agent) to do the Phase 1 work, give it this exact prompt:

> **Task:** Implement Phase 1 from `docs/PHASE_1_BRIEF.md`.
>
> **Scope:** Phase 1 only — do not touch Phases 2-4.
>
> **Reference implementations** are in `docs/REFERENCE_TTS_RS.md`. Adapt them into the existing `tts.rs` structure rather than copy-pasting verbatim.
>
> **Read `CONTRIBUTING.md` before opening a PR.**

That last line is important. Without it, agents tend to either copy reference code verbatim (which breaks the existing module structure) or ignore it entirely (which means they reinvent it badly).

## Troubleshooting

**Script says "Source not found":** edit the `$src` path at the top of `package-for-github.ps1` to point at wherever your `nerve-main\nerve-main` folder actually lives.

**Script says "Dropin folder not found":** you ran it from somewhere other than the dropin folder, OR you renamed/moved the dropin folder. Either `cd` into it first or edit `$dropin` at the top of the script.

**Git push rejected:** the GitHub repo isn't actually empty. If you're sure you want to overwrite it, the `--force` flag in the printed commands handles this. If you're not sure, abort and check the repo on GitHub first.

**Codex starts implementing Phase 2/3/4 anyway:** stop it. Re-prompt with "Phase 1 ONLY. Read PHASE_1_BRIEF.md again." If it still won't stay in scope, that's a sign the agent isn't following the brief and you need a different agent (or a more explicit prompt).

## What happens after Phase 1 ships

When Codex's PR is merged and the TTS fix is verified working on your machine (19+ voices in the dropdown, no `ERROR: interrupted`, Edge voices visible), come back and we'll write the Phase 2 brief for the Cloudflare sync layer. That's its own scoped session — D1 schema, Worker API, R2 layout, auth model, sync semantics. Don't try to design it now while you're still fixing TTS.

One thing at a time. Phase 1 first. Everything else follows.
