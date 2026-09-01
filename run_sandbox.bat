@echo off
cd /d "%~dp0"
set WORK_TOOL_ENV=sandbox
set WORK_TOOL_PORT=5001
set WORK_TOOL_DATA_DIR=%~dp0data\sandbox
set PAUSE_AUTOMATED_TASKS=1
python flask_endpoints.py
