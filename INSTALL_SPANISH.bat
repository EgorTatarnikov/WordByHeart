@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -m scripts.setup --language es
exit /b %ERRORLEVEL%
:missing
powershell.exe -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Сначала запустите INSTALL.bat для установки WordByHeart.','WordByHeart')" >nul
exit /b 1
