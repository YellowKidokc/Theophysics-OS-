# package-for-github.ps1
# Merges your local nerve-main Rust source into the prepared GitHub dropin folder
# and stages everything ready for `git init` and push to YellowKidokc/nerve.
#
# PREREQUISITES:
#   1. The nerve-github-dropin folder must be present (this is what you downloaded
#      from Claude — it contains README.md, docs/, CONTRIBUTING.md, .gitignore).
#   2. Your local nerve source must be at C:\Users\lowes\Downloads\nerve-main\nerve-main
#      (adjust $src below if it's elsewhere).
#
# WHAT IT DOES:
#   - Copies src/*.rs from your local source into the dropin
#   - Copies html/*.html from your local source into the dropin
#   - Copies Cargo.toml and build.bat from your local source into the dropin
#   - Leaves all the docs Claude prepared (README, docs/, CONTRIBUTING) in place
#   - Prints the exact git commands to push to YellowKidokc/nerve
#
# Run from PowerShell. No admin required.

$ErrorActionPreference = "Stop"

# === CONFIGURE THESE IF YOUR PATHS DIFFER ===
$src    = "D:\Clipboard sync"
$dropin = "C:\Users\lowes\Downloads\nerve-github-dropin\nerve-github-dropin"
# ============================================

Write-Host ""
Write-Host "Nerve GitHub Package Builder" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan
Write-Host ""

# Sanity checks
if (-not (Test-Path $src)) {
    Write-Host "ERROR: Source not found at $src" -ForegroundColor Red
    Write-Host "Edit the `$src variable at the top of this script." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $dropin)) {
    Write-Host "ERROR: Dropin folder not found at $dropin" -ForegroundColor Red
    Write-Host "Make sure you've extracted the nerve-github-dropin folder from Claude." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path "$dropin\README.md")) {
    Write-Host "ERROR: $dropin exists but doesn't contain README.md" -ForegroundColor Red
    Write-Host "This doesn't look like the prepared dropin folder. Aborting." -ForegroundColor Yellow
    exit 1
}

Write-Host "Source:  $src" -ForegroundColor Gray
Write-Host "Dropin:  $dropin" -ForegroundColor Gray
Write-Host ""

# Make sure target dirs exist in the dropin
New-Item -ItemType Directory -Path "$dropin\src" -Force | Out-Null
New-Item -ItemType Directory -Path "$dropin\html" -Force | Out-Null

# Copy Rust source
Write-Host "[1/4] Copying Rust source..." -ForegroundColor Cyan
$rust_files = Get-ChildItem "$src\src\*.rs" -ErrorAction SilentlyContinue
if ($rust_files.Count -eq 0) {
    Write-Host "  WARNING: No .rs files found in $src\src" -ForegroundColor Yellow
} else {
    foreach ($f in $rust_files) {
        Copy-Item $f.FullName "$dropin\src\$($f.Name)" -Force
        Write-Host "  + src\$($f.Name)" -ForegroundColor DarkGray
    }
}

# Copy Cargo files
Write-Host "[2/4] Copying Cargo manifest..." -ForegroundColor Cyan
if (Test-Path "$src\Cargo.toml") {
    Copy-Item "$src\Cargo.toml" "$dropin\Cargo.toml" -Force
    Write-Host "  + Cargo.toml" -ForegroundColor DarkGray
} else {
    Write-Host "  WARNING: Cargo.toml not found at $src" -ForegroundColor Yellow
}

# Copy build script
if (Test-Path "$src\build.bat") {
    Copy-Item "$src\build.bat" "$dropin\build.bat" -Force
    Write-Host "  + build.bat" -ForegroundColor DarkGray
}

# Copy HTML
Write-Host "[3/4] Copying HTML..." -ForegroundColor Cyan
$html_files = Get-ChildItem "$src\html\*.html" -ErrorAction SilentlyContinue
if ($html_files.Count -eq 0) {
    Write-Host "  WARNING: No .html files found in $src\html" -ForegroundColor Yellow
} else {
    foreach ($f in $html_files) {
        Copy-Item $f.FullName "$dropin\html\$($f.Name)" -Force
        Write-Host "  + html\$($f.Name)" -ForegroundColor DarkGray
    }
}

# Verify what we have
Write-Host "[4/4] Verifying dropin contents..." -ForegroundColor Cyan
$expected = @(
    "README.md",
    "CONTRIBUTING.md",
    ".gitignore",
    "docs\REFERENCE_TTS_RS.md",
    "docs\ARCHITECTURE.md",
    "docs\HISTORICAL_FIXES.md",
    "docs\PHASE_1_BRIEF.md"
)

$missing = @()
foreach ($e in $expected) {
    if (-not (Test-Path "$dropin\$e")) {
        $missing += $e
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "WARNING: The following expected files are missing from the dropin:" -ForegroundColor Yellow
    foreach ($m in $missing) {
        Write-Host "  - $m" -ForegroundColor Yellow
    }
    Write-Host "The dropin folder may be incomplete. Continuing anyway..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "Package ready at: $dropin" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Final tree:" -ForegroundColor Cyan
Get-ChildItem $dropin -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($dropin.Length + 1)
    Write-Host "  $rel" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  cd `"$dropin`"" -ForegroundColor White
Write-Host "  git init" -ForegroundColor White
Write-Host "  git add ." -ForegroundColor White
Write-Host "  git commit -m `"Initial canonical package: Phase 1 TTS dual-hive fix scoped`"" -ForegroundColor White
Write-Host "  git branch -M main" -ForegroundColor White
Write-Host "  git remote add origin https://github.com/YellowKidokc/nerve.git" -ForegroundColor White
Write-Host "  git push -u origin main --force" -ForegroundColor White
Write-Host ""
Write-Host "The --force on the first push is intentional — it overwrites the empty" -ForegroundColor Gray
Write-Host "starter repo on GitHub with this canonical version." -ForegroundColor Gray
Write-Host ""
Write-Host "After pushing, point Codex at the repo with this exact prompt:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Task: Implement Phase 1 from docs/PHASE_1_BRIEF.md." -ForegroundColor White
Write-Host "  Scope: Phase 1 only — do not touch Phases 2-4." -ForegroundColor White
Write-Host "  Reference implementations are in docs/REFERENCE_TTS_RS.md." -ForegroundColor White
Write-Host "  Adapt them into the existing tts.rs structure rather than" -ForegroundColor White
Write-Host "  copy-pasting verbatim. Read CONTRIBUTING.md before opening a PR." -ForegroundColor White
Write-Host ""
Write-Host "Don't forget to archive YellowKidokc/nerve-1 on GitHub" -ForegroundColor Yellow
Write-Host "(Settings → Archive this repository) so it doesn't become a zombie." -ForegroundColor Yellow
Write-Host ""
