@echo off
cd /d "%~dp0.."
echo Synth Head Config UI
echo Repo: %CD%
if not exist "data\config" (
  echo ERROR: data\config not found — run this from config_ui\open.bat inside the HeadGen repo.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\pip.exe install -q -r config_ui\requirements.txt
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8420 .*LISTENING"') do (
  echo Stopping previous config UI on port 8420 ^(PID %%p^)...
  taskkill /PID %%p /F >nul 2>&1
)
start http://127.0.0.1:8420
.venv\Scripts\python.exe -m config_ui.server
