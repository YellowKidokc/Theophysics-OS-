@echo off
setlocal
cd /d "%~dp0"
python SCRIPTS\check_wiki_layer.py
endlocal
