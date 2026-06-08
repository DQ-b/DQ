@echo off
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\HI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "fu2609_dashboard.py" --host 127.0.0.1 --port 8765
pause
