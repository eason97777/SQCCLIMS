$ErrorActionPreference = "Stop"

$InstallDir = "F:\soft\JIQT"
$ServiceExe = Join-Path $InstallDir "JIQTService.exe"

if (Test-Path -LiteralPath $ServiceExe) {
    & $ServiceExe stop
    & $ServiceExe uninstall
}
