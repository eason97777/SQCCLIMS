# JIQT Installer Build

Install Inno Setup 6 first:

```text
https://jrsoftware.org/isdl.php
```

Build installer:

```powershell
cd D:\BaiduSyncdisk\Code\JIQT_2\SCRmonitor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File packaging\installer\build-installer.ps1
```

Output:

```text
D:\BaiduSyncdisk\Code\JIQT_2\SCRmonitor\packaging\output\JIQT_Setup_1.0.0.exe
```

Build update package with the same staging files by opening `JIQT_Update.iss` in Inno Setup Compiler, or changing the script to compile that file.

The installer writes the app to:

```text
F:\soft\JIQT
```

Runtime data is kept in:

```text
F:\soft\JIQTData
```

Uninstalling the app does not delete `F:\soft\JIQTData`.

If the compiler is not found, install Inno Setup 6 and rerun the build command.
