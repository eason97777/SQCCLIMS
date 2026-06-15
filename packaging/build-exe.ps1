param(
    [string]$ReleaseRoot = "F:\soft\SQCCLIMS"
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$AppRoot = Join-Path $ReleaseRoot "app"
$BuildRoot = Join-Path $SourceRoot "build"
$DistRoot = Join-Path $SourceRoot "dist"

python -m PyInstaller --version | Out-Null

Set-Location $SourceRoot
python -m PyInstaller `
    --noconfirm `
    --clean `
    --name server `
    --distpath $DistRoot `
    --workpath $BuildRoot `
    --add-data "parsers;parsers" `
    --add-data "migrations;migrations" `
    --add-data "templates;templates" `
    --add-data "frontend\dist;frontend\dist" `
    server.py

New-Item -ItemType Directory -Force -Path $AppRoot | Out-Null
Copy-Item -Path (Join-Path $DistRoot "server\*") -Destination $AppRoot -Recurse -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\SQCCLIMSService.xml") -Destination (Join-Path $ReleaseRoot "SQCCLIMSService.xml") -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\install-service.ps1") -Destination (Join-Path $ReleaseRoot "install-service.ps1") -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\uninstall-service.ps1") -Destination (Join-Path $ReleaseRoot "uninstall-service.ps1") -Force
Copy-Item -Path (Join-Path $SourceRoot "tools") -Destination (Join-Path $ReleaseRoot "tools") -Recurse -Force

Write-Host "Executable release copied to $ReleaseRoot"
