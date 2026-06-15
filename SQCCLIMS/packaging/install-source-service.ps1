$ErrorActionPreference = "Stop"

$ServiceName = "SQCCLIMSService"
$InstallDir = $env:LIMS_INSTALL_DIR
if (-not $InstallDir) {
    $InstallDir = "F:\soft\SQCCLIMS"
}
$Runner = Join-Path $InstallDir "run-source-service.ps1"
$HiddenLauncher = Join-Path $InstallDir "start-hidden.vbs"

if (-not (Test-Path -LiteralPath $Runner)) {
    throw "Missing runner: $Runner"
}

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    if ($existingService.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force
    }
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}

Unregister-ScheduledTask -TaskName $ServiceName -Confirm:$false -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $HiddenLauncher) {
    $Action = New-ScheduledTaskAction `
        -Execute "wscript.exe" `
        -Argument "`"$HiddenLauncher`""
} else {
    $Action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`""
}

$Trigger = New-ScheduledTaskTrigger -AtLogOn

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $ServiceName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Description "SQCCLIMS background service" `
    -Force | Out-Null

netsh advfirewall firewall add rule name="SQCCLIMS Backend 8000" dir=in action=allow protocol=TCP localport=8000 | Out-Null
Start-ScheduledTask -TaskName $ServiceName
