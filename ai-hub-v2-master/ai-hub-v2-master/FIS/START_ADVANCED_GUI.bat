@echo off
setlocal
title River FIS - Advanced GUI

set "PORT=8450"
set "URL=http://127.0.0.1:%PORT%/"

cd /d "%~dp0"

echo.
echo  River FIS - Advanced GUI
echo  Starting local file intelligence workbench...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  Python was not found. Install Python, then run this again.
    pause
    exit /b 1
)

if not exist "api_server.py" (
    echo  api_server.py is missing from this folder.
    pause
    exit /b 1
)

if not exist "index.html" (
    echo  index.html is missing from this folder.
    pause
    exit /b 1
)

echo  Checking Python packages...
python -c "import yake, numpy, sklearn, yaml" >nul 2>&1
if errorlevel 1 (
    echo  Installing required packages. This may take a minute the first time.
    python -m pip install -q yake numpy scikit-learn pyyaml
    if errorlevel 1 (
        echo  Package install failed. Check Python and pip, then run this again.
        pause
        exit /b 1
    )
)

if not exist "\\192.168.2.50\brain\09_DATABASES\FIS" (
    mkdir "\\192.168.2.50\brain\09_DATABASES\FIS" >nul 2>&1
)

echo  Starting server on port %PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=(Get-Location).Path; $port=%PORT%; $health=('http://127.0.0.1:'+$port+'/api/health'); $ok=$false; try { $r=Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -eq 200){ $ok=$true } } catch {}; if(-not $ok){ $listeners=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach($conn in $listeners){ Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue }; Start-Sleep -Milliseconds 500; Start-Process -FilePath 'python' -ArgumentList @('api_server.py',[string]$port) -WorkingDirectory $root -WindowStyle Minimized }; $ok=$false; for($i=0; $i -lt 24; $i++){ try { $r=Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep -Milliseconds 500 }; if(-not $ok){ exit 2 }"
if errorlevel 1 (
    echo  Server did not answer. Close old Python windows and try again.
    pause
    exit /b 1
)

echo  Opening %URL%
start "" "%URL%"

echo.
echo  Advanced GUI is open.
echo  Keep the small Python server window running while you use it.
echo.
pause
