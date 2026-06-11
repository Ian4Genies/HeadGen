@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\pip.exe install -q -r config_ui\requirements.txt
start http://127.0.0.1:8420
.venv\Scripts\python.exe -m config_ui.server
