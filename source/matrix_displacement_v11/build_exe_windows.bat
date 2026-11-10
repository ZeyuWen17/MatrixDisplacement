@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_exe_windows.ps1"
if errorlevel 1 (
  echo [ERROR] Windows EXE build failed. Check messages above.
  pause
  exit /b 1
)
echo [OK] Review docs\V1.1_WINDOWS_ACCEPTANCE.md before release.
pause
