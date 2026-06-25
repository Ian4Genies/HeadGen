@echo off
setlocal
cd /d "%~dp0.."
echo Synth Head Config UI
echo Repo: %CD%

if not exist "data\config" (
  echo ERROR: data\config not found — run config_ui\open.bat from inside the HeadGen repo.
  pause
  exit /b 1
)

set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  echo ERROR: Python not found. Install Python 3.11+ and add it to PATH, or install the py launcher.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create .venv — check that Python 3.11+ is installed.
    pause
    exit /b 1
  )
)

echo Installing dependencies...
".venv\Scripts\pip.exe" install -q -r config_ui\requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed — see messages above.
  pause
  exit /b 1
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8420 .*LISTENING"') do (
  echo Stopping previous config UI on port 8420 ^(PID %%p^)...
  taskkill /PID %%p /F >nul 2>&1
)

echo Starting server at http://127.0.0.1:8420
start "" http://127.0.0.1:8420
".venv\Scripts\python.exe" -m config_ui.server
if errorlevel 1 (
  echo.
  echo Server exited with an error.
  pause
  exit /b 1
)
