param(
    [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "This release pipeline targets Windows only. Run it on Windows 10/11."
}

Write-Host "Building C.P.S. standalone Windows desktop application..." -ForegroundColor Cyan
& $Python -m pip install --requirement requirements.lock
& $Python -m pip install --no-deps --no-build-isolation --editable .
& $Python scripts/package_release.py
& $Python -m PyInstaller --clean --noconfirm packaging/cps.spec

$Artifact = Join-Path $ProjectRoot "dist\CPS\CPS.exe"
if (-not (Test-Path $Artifact)) {
    throw "PyInstaller did not produce the expected artifact: $Artifact"
}
Write-Host "PyInstaller artifact: $Artifact" -ForegroundColor Green
& $Python scripts/package_desktop.py
$Version = & $Python -c "import cps; print(cps.__version__)"
$Portable = Join-Path $ProjectRoot "dist\cps-desktop-v$Version-windows-x64.zip"

if ($BuildInstaller) {
    $Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($null -eq $Iscc) {
        throw "Inno Setup compiler (ISCC.exe) is not installed; refusing to create a fake installer."
    }
    & $Iscc.Source (Join-Path $ProjectRoot "installer\CPS.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE"
    }
    Write-Host "Inno Setup installer created under dist\installer" -ForegroundColor Green
    $Installer = Get-ChildItem (Join-Path $ProjectRoot "dist\installer") -Filter *.exe | Select-Object -First 1
    if ($null -eq $Installer) {
        throw "Inno Setup did not produce an installer executable."
    }
}

$Artifacts = @(Get-ChildItem (Join-Path $ProjectRoot "dist") -Filter *.zip | Select-Object -ExpandProperty FullName)
if ($BuildInstaller) {
    $Artifacts += $Installer.FullName
}
& $Python scripts/write_checksums.py $Artifacts
