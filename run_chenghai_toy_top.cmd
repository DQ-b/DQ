@echo off
setlocal
set "CHENGHAI_INPUT_DIR=%~dp0input_csv"
set "CHENGHAI_OUTPUT_DIR=%~dp0outputs\chenghai_toy_top"
"C:\Users\HI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "%~dp0chenghai_toy_top_pipeline.py"
pause
