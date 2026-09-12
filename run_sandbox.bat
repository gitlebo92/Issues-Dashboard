@echo off
cd /d "%~dp0"
set WORK_TOOL_ENV=sandbox
set WORK_TOOL_PORT=5001
set WORK_TOOL_DATA_DIR=%~dp0data\sandbox
set PAUSE_AUTOMATED_TASKS=1
rem Sandbox stays on loopback — dev/test does not need to be reachable from
rem other machines. Set 0.0.0.0 if you need to test LAN access.
set WORK_TOOL_BIND=127.0.0.1
python flask_endpoints.py
