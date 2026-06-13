@echo off
python "%~dp0SCRIPTS\run_packet.py" --topic "%~1" --graph "%~2" --out "%~3"
pause
