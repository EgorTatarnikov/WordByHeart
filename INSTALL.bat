@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
set "SETUP_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %SETUP_RESULT%
