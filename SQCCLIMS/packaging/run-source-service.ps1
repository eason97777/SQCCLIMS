$ErrorActionPreference = "Stop"

$InstallDir = $env:LIMS_INSTALL_DIR
if (-not $InstallDir) {
    $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$AppDir = Join-Path $InstallDir "app"
$DataDir = $env:LIMS_DATA_DIR
if (-not $DataDir) {
    $DataDir = "F:\soft\SQCCLIMSData"
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "uploads") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "outputs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "backups") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "logs") | Out-Null

Set-Location $AppDir
python server.py --host 0.0.0.0 --port 8000 --data-dir $DataDir
