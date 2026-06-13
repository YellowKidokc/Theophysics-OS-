# ================================================
# SUBSTACK BATCH PUBLISHER
# Processes multiple papers for Substack publishing
# ================================================

param(
    [string]$InputFolder = ".\OUTBOX",
    [string]$OutputFolder = ".\SUBSTACK_READY",
    [switch]$OpenBrowser,
    [switch]$CopyFirst
)

# Create output folder if it doesn't exist
if (!(Test-Path $OutputFolder)) {
    New-Item -ItemType Directory -Path $OutputFolder | Out-Null
}

Write-Host ""
Write-Host "========================================"
Write-Host "   SUBSTACK BATCH PUBLISHER"
Write-Host "========================================"
Write-Host ""

# Check for pandoc
$pandocPath = Get-Command pandoc -ErrorAction SilentlyContinue
if (!$pandocPath) {
    Write-Host "ERROR: Pandoc not found. Install with: winget install JohnMacFarlane.Pandoc" -ForegroundColor Red
    exit 1
}

# Find all markdown/txt files in OUTBOX
$files = Get-ChildItem -Path $InputFolder -Include "*.md", "*_normalized.txt" -Recurse | 
         Where-Object { $_.Name -notmatch "README|GUIDE|INSTRUCTIONS" }

if ($files.Count -eq 0) {
    Write-Host "No markdown or normalized text files found in $InputFolder" -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($files.Count) files to process:"
Write-Host ""

$processed = @()

foreach ($file in $files) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $htmlFile = Join-Path $OutputFolder "$baseName.html"
    
    Write-Host "  Processing: $($file.Name)" -ForegroundColor Cyan
    
    # Convert to HTML
    $content = Get-Content -Raw $file.FullName
    $html = $content | pandoc -f markdown -t html
    
    # Save HTML file
    $html | Out-File -FilePath $htmlFile -Encoding UTF8
    
    $processed += @{
        Name = $baseName
        Source = $file.FullName
        HTML = $htmlFile
        Size = (Get-Item $htmlFile).Length
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "   PROCESSING COMPLETE"
Write-Host "========================================"
Write-Host ""
Write-Host "HTML files ready in: $OutputFolder"
Write-Host ""

# List processed files
Write-Host "Files ready for Substack:" -ForegroundColor Green
foreach ($p in $processed) {
    Write-Host "  - $($p.Name)" 
}

# Copy first file to clipboard if requested
if ($CopyFirst -and $processed.Count -gt 0) {
    $firstHtml = Get-Content -Raw $processed[0].HTML
    Set-Clipboard $firstHtml
    Write-Host ""
    Write-Host "First file copied to clipboard: $($processed[0].Name)" -ForegroundColor Yellow
}

# Open Substack if requested
if ($OpenBrowser) {
    Start-Process "https://substack.com/home"
}

Write-Host ""
Write-Host "To copy any file to clipboard, run:"
Write-Host "  Get-Content '.\SUBSTACK_READY\filename.html' | Set-Clipboard"
Write-Host ""
