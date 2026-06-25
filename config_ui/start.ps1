$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path "data\config")) {
    Write-Error "data\config not found — run from inside the HeadGen repo."
}

$py = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py -3" }
else { throw "Python not found. Install Python 3.11+ and add it to PATH." }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating venv..."
    Invoke-Expression "$py -m venv .venv"
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\pip.exe install -q -r config_ui\requirements.txt

Write-Host "Starting config UI at http://127.0.0.1:8420"
Start-Process "http://127.0.0.1:8420"
& .\.venv\Scripts\python.exe -m config_ui.server
