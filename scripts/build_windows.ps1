$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Building C.P.S. Standalone Windows Desktop Application..." -ForegroundColor Cyan

# Ensure dependencies are installed
python -m pip install -e ".[dev]"

# Run PyInstaller package build
python -m PyInstaller --noconfirm --windowed --name "CPS" --add-data "extension;extension" app.py

Write-Host "Build output created at: $ProjectRoot\dist\CPS" -ForegroundColor Green
