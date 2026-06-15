$ErrorActionPreference = "Stop"

$InstallDir = $env:JIQT_INSTALL_DIR
if (-not $InstallDir) {
    $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$AppDir = Join-Path $InstallDir "app"
$DataDir = $env:JIQT_DATA_DIR
if (-not $DataDir) {
    $DataDir = "F:\soft\JIQTData"
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "uploads") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "outputs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "backups") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "logs") | Out-Null

Set-Location $AppDir
python server.py --host 0.0.0.0 --port 8000 --data-dir $DataDir
