Option Explicit

Dim shell, fso, scriptDir, runner, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
runner = fso.BuildPath(scriptDir, "run-source-service.ps1")

command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & runner & Chr(34)
shell.Run command, 0, False
