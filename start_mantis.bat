@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_mantis.ps1"
if errorlevel 1 (
  echo.
  echo MANTIS could not start. Review the error above.
  pause
)
