@echo off
cd /d "%~dp0"
rem NOTE: the live dashboard normally runs as the Windows service
rem "IssuesDashboard", which starts flask_endpoints.py directly and does NOT
rem read this file. Use this only to run :5000 by hand. Service-wide settings
rem belong in .env, which the service does read.
set WORK_TOOL_ENV=live
set WORK_TOOL_PORT=5000
set WORK_TOOL_DATA_DIR=
set PAUSE_AUTOMATED_TASKS=1
python flask_endpoints.py
