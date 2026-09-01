@echo off
cd /d "%~dp0"
set WORK_TOOL_ENV=live
set WORK_TOOL_PORT=5000
set WORK_TOOL_DATA_DIR=
set PAUSE_AUTOMATED_TASKS=1
python flask_endpoints.py
