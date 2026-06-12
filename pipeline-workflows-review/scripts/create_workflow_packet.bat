@echo off
setlocal
cd /d "%~dp0\.."
if "%~1"=="" (
  echo Usage: scripts\create_workflow_packet.bat WorkflowName
  exit /b 1
)
python scripts\create_workflow_packet.py %1
