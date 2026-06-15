param(
    [string]$InnoSetupCompiler = ""
)

$ErrorActionPreference = "Stop"

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackagingDir = Split-Path -Parent $InstallerDir
$SourceRoot = Split-Path -Parent $PackagingDir
$StagingRoot = Join-Path $PackagingDir "staging\JIQT"
$OutputRoot = Join-Path $PackagingDir "output"

Remove-Item -LiteralPath $StagingRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $StagingRoot | Out-Null
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PackagingDir "build-source-release.ps1") -ReleaseRoot $StagingRoot

if (-not $InnoSetupCompiler) {
    $candidatePaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "F:\soft\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidatePaths) {
        if (Test-Path -LiteralPath $candidate) {
            $InnoSetupCompiler = $candidate
            break
        }
    }
}

if (-not $InnoSetupCompiler) {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        $InnoSetupCompiler = $command.Source
    }
}

if (-not $InnoSetupCompiler -or -not (Test-Path -LiteralPath $InnoSetupCompiler)) {
    throw "Inno Setup compiler not found. Install Inno Setup 6, then rerun this script."
}

& $InnoSetupCompiler (Join-Path $InstallerDir "JIQT_Setup.iss")

Write-Host "Installer output: $OutputRoot"
