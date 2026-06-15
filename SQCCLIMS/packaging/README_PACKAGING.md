# SQCCLIMS Packaging Notes

## Source Release

Use this first if Python is installed on the target computer.

```powershell
cd D:\BaiduSyncdisk\Code\SCRmonitor\SQCCLIMS
powershell.exe -NoProfile -ExecutionPolicy Bypass -File packaging\build-source-release.ps1
```

This copies the runtime package to:

```text
F:\soft\SQCCLIMS
```

Run it manually:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\soft\SQCCLIMS\run-source-service.ps1
```

Install it as a Windows service:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\soft\SQCCLIMS\install-source-service.ps1
```

## EXE Release

Install build dependencies on the build computer:

```powershell
cd D:\BaiduSyncdisk\Code\SCRmonitor\SQCCLIMS
python -m pip install -r requirements.txt
```

Build:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File packaging\build-exe.ps1
```

This copies the executable runtime package to:

```text
F:\soft\SQCCLIMS
```

## Runtime Data

Business data is stored outside the app package:

```text
F:\soft\SQCCLIMSData
```

Do not overwrite this directory during updates.
