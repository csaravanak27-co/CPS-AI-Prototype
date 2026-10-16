$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

python -m pip install -e ".[dev]"
python -m PyInstaller --noconfirm --windowed --name VulnQuestAI app.py
Write-Host "Build output: $ProjectRoot\dist\VulnQuestAI"
