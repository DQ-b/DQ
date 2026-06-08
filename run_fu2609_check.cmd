@echo off
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\HI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "fu2609_check.py" --symbol FU2609 --ai
echo.
pause
