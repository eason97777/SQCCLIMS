param(
    [string]$ReleaseRoot = "F:\soft\JIQT"
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$AppRoot = Join-Path $ReleaseRoot "app"

New-Item -ItemType Directory -Force -Path $AppRoot | Out-Null

Copy-Item -Path (Join-Path $SourceRoot "server.py") -Destination $AppRoot -Force
Copy-Item -Path (Join-Path $SourceRoot "parsers") -Destination $AppRoot -Recurse -Force
Copy-Item -Path (Join-Path $SourceRoot "migrations") -Destination $AppRoot -Recurse -Force
Copy-Item -Path (Join-Path $SourceRoot "templates") -Destination $AppRoot -Recurse -Force
Copy-Item -Path (Join-Path $SourceRoot "frontend\dist") -Destination (Join-Path $AppRoot "frontend\dist") -Recurse -Force
Copy-Item -Path (Join-Path $SourceRoot "requirements.txt") -Destination $AppRoot -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\run-source-service.ps1") -Destination (Join-Path $ReleaseRoot "run-source-service.ps1") -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\start-hidden.vbs") -Destination (Join-Path $ReleaseRoot "start-hidden.vbs") -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\install-source-service.ps1") -Destination (Join-Path $ReleaseRoot "install-source-service.ps1") -Force
Copy-Item -Path (Join-Path $SourceRoot "packaging\uninstall-source-service.ps1") -Destination (Join-Path $ReleaseRoot "uninstall-source-service.ps1") -Force
Copy-Item -Path (Join-Path $SourceRoot "tools") -Destination (Join-Path $ReleaseRoot "tools") -Recurse -Force

Write-Host "Source release copied to $AppRoot"
