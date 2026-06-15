#define MyAppName "SQCCLIMS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SQCCLIMS"
#define MyDefaultDir "F:\soft\SQCCLIMS"
#define MyDataDir "F:\soft\SQCCLIMSData"
#define MySourceRoot "..\..\"
#define MyReleaseRoot "..\staging\SQCCLIMS"

[Setup]
AppId={{8A7BB03A-9D1E-4F79-840E-1438F478D6E7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={#MyDefaultDir}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\output
OutputBaseFilename=SQCCLIMS_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\tools\open-local.ps1

[Files]
Source: "{#MyReleaseRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{#MyDataDir}"
Name: "{#MyDataDir}\uploads"
Name: "{#MyDataDir}\outputs"
Name: "{#MyDataDir}\backups"
Name: "{#MyDataDir}\logs"

[Icons]
Name: "{group}\Open SQCCLIMS"; Filename: "http://127.0.0.1:8000"
Name: "{commondesktop}\Open SQCCLIMS"; Filename: "http://127.0.0.1:8000"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional tasks:"; Flags: checkedonce

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install-source-service.ps1"""; Flags: runhidden waituntilterminated
Filename: "http://127.0.0.1:8000"; Description: "Open SQCCLIMS"; Flags: postinstall shellexec skipifsilent nowait

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall-source-service.ps1"""; Flags: runhidden waituntilterminated

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    MsgBox('SQCCLIMS has been uninstalled. Business data was not removed: {#MyDataDir}', mbInformation, MB_OK);
  end;
end;
