@echo off
setlocal
cd /d "%~dp0"
python SCRIPTS\run_packet.py --mode stage
pause
