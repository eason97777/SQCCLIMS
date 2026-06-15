#define MyAppName "SQCCLIMS"
#define MyAppVersion "1.0.4"
#define MyDefaultDir "F:\soft\SQCCLIMS"
#define MyReleaseRoot "..\staging\SQCCLIMS"

[Setup]
AppId={{8A7BB03A-9D1E-4F79-840E-1438F478D6E7}
AppName={#MyAppName} Update
AppVersion={#MyAppVersion}
DefaultDirName={#MyDefaultDir}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\output
OutputBaseFilename=SQCCLIMS_Update_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Files]
Source: "{#MyReleaseRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Stop-ScheduledTask -TaskName SQCCLIMSService -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install-source-service.ps1"""; Flags: runhidden waituntilterminated
