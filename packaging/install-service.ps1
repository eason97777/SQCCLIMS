$ErrorActionPreference = "Stop"

$InstallDir = "F:\soft\SQCCLIMS"
$DataDir = "F:\soft\SQCCLIMSData"
$ServiceExe = Join-Path $InstallDir "SQCCLIMSService.exe"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "uploads") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "outputs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "backups") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "logs") | Out-Null

netsh advfirewall firewall add rule name="SQCCLIMS Backend 8000" dir=in action=allow protocol=TCP localport=8000 | Out-Null

if (-not (Test-Path -LiteralPath $ServiceExe)) {
    throw "Missing service wrapper: $ServiceExe"
}

& $ServiceExe install
& $ServiceExe start
