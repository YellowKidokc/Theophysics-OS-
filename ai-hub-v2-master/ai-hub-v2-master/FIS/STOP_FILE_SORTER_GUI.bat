@echo off
setlocal
title River FIS - Stop Server

set "PORT=8450"

echo.
echo  River FIS - Stop Server
echo  Looking for the local server on port %PORT%...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$port=%PORT%; $listeners=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if(-not $listeners){ Write-Host 'No River FIS server is running.'; exit 0 }; foreach($conn in $listeners){ try { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop; Write-Host ('Stopped process '+$conn.OwningProcess) } catch { Write-Host ('Could not stop process '+$conn.OwningProcess) } }"

echo.
pause
