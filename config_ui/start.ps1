$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating venv..."
    python -m venv .venv
}

& .\.venv\Scripts\pip.exe install -q -r config_ui\requirements.txt

Write-Host "Starting config UI at http://127.0.0.1:8420"
& .\.venv\Scripts\python.exe -m config_ui.server
