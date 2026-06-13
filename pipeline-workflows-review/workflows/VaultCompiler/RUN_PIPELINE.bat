@echo off
echo === Vault Compiler ===
echo Source: %1
echo Output: %2
python "%~dp0SCRIPTS\compile_folder.py" --source "%1" --output "%2"
echo === Done ===
pause
