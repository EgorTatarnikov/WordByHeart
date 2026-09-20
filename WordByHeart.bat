@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto missing
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -c "import tkinter; import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if errorlevel 1 goto missing
start "" ".venv\Scripts\pythonw.exe" "%~dp0scripts\launch.pyw"
exit /b 0
:missing
powershell.exe -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Run INSTALL.bat to install or repair WordByHeart.','WordByHeart')" >nul
exit /b 1
