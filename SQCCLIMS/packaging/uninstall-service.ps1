$ErrorActionPreference = "Stop"

$InstallDir = "F:\soft\SQCCLIMS"
$ServiceExe = Join-Path $InstallDir "SQCCLIMSService.exe"

if (Test-Path -LiteralPath $ServiceExe) {
    & $ServiceExe stop
    & $ServiceExe uninstall
}
