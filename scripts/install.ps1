# Bootstrap only. Remaining setup runs with the project's .venv Python.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

function Test-Python([string]$Exe) {
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { return $null }
    try {
        $answer = & $Exe -c "import sys,struct,platform; import tkinter,venv,ensurepip; assert (3,11)<=sys.version_info<(3,14) and struct.calcsize('P')==8 and platform.machine().lower() in ('amd64','x86_64'); print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0) { return ($answer | Select-Object -Last 1) }
    } catch {}
    return $null
}

function Find-Python {
    $existing = Test-Python (Join-Path $projectRoot ".venv\Scripts\python.exe")
    if ($existing) { return $existing }
    foreach ($name in @("python.exe", "python3.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notlike "*WindowsApps*") {
            $candidate = Test-Python $command.Source
            if ($candidate) { return $candidate }
        }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($version in @("-3.12", "-3.13", "-3.11")) {
            try {
                $candidate = & $launcher.Source $version -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $found = Test-Python ($candidate | Select-Object -Last 1)
                    if ($found) { return $found }
                }
            } catch {}
        }
    }
    foreach ($base in @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles\Python")) {
        foreach ($path in @(Get-ChildItem -LiteralPath $base -Filter "Python3*" -Directory -ErrorAction SilentlyContinue)) {
            $found = Test-Python (Join-Path $path.FullName "python.exe")
            if ($found) { return $found }
        }
    }
    return $null
}

try {
    Write-Host "WordByHeart Setup"
    Write-Host "[1/7] Проверка Python..."
    if (-not [Environment]::Is64BitOperatingSystem) { throw "Нужна 64-разрядная Windows." }
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        Write-Host "Совместимый Python не найден. Устанавливается официальный Python 3.13.15 (x64) для текущего пользователя."
        $downloadDir = Join-Path $projectRoot ".local\downloads"
        New-Item -ItemType Directory -Path $downloadDir -Force | Out-Null
        $installer = Join-Path $downloadDir "python-3.13.15-amd64.exe"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe" -OutFile $installer -TimeoutSec 300
        $expected = "edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403"
        if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
            throw "Контрольная сумма установщика Python не совпала. Повторите INSTALL.bat."
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne "Valid") { throw "Не удалось проверить подпись установщика Python." }
        $installProcess = Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_tcltk=1 Include_pip=1" -WindowStyle Hidden -Wait -PassThru
        if ($installProcess.ExitCode -notin @(0, 3010)) { throw "Python: код установки $($installProcess.ExitCode)." }
        $pythonExe = Find-Python
        if (-not $pythonExe) { throw "Python не найден после установки. Установите x64 Python 3.11–3.13 с python.org (с Tcl/Tk), затем повторите INSTALL.bat." }
    }
    Write-Host "Python: $pythonExe"
    Write-Host "[2/7] Проверка виртуального окружения..."
    $venvDir = Join-Path $projectRoot ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $valid = Test-Python $venvPython
    if ($valid) {
        & $venvPython -c "import sys,pip; from pathlib import Path; assert sys.prefix != sys.base_prefix; assert Path(sys.prefix).resolve() == Path('.venv').resolve(); assert Path(sys.executable).with_name('pythonw.exe').is_file()" 2>$null
        $valid = $LASTEXITCODE -eq 0
    }
    if (-not $valid) {
        if (Test-Path -LiteralPath $venvDir) {
            # Preserve damaged environments. Verify containment before moving.
            $resolved = (Resolve-Path -LiteralPath $venvDir).Path
            if ((Split-Path -Parent $resolved) -ne $projectRoot) { throw "Небезопасный путь .venv." }
            if ((Get-Item -LiteralPath $venvDir).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw ".venv является ссылкой. Используйте обычный локальный каталог." }
            # Choose a base interpreter outside .venv before moving its files.
            $baseExe = & $pythonExe -c "import sys; print(sys._base_executable)"
            $pythonExe = Test-Python ($baseExe | Select-Object -Last 1)
            if (-not $pythonExe) { throw "Не найден базовый Python. Установите Python и повторите INSTALL.bat." }
            $backup = Join-Path $projectRoot (".venv.broken-" + [guid]::NewGuid().ToString("N"))
            if ((Split-Path -Parent $backup) -ne $projectRoot) { throw "Небезопасный путь резервной копии." }
            Move-Item -LiteralPath $resolved -Destination $backup
            Write-Host "Старое окружение сохранено в $backup"
        }
        & $pythonExe -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw "Не удалось создать .venv." }
    }
    & $venvPython -m scripts.setup
    if ($LASTEXITCODE -ne 0) { throw "Установка не завершена. Проверьте сообщение выше и logs\setup.log; повторите INSTALL.bat." }
    Write-Host "Установка завершена. Для запуска используйте WordByHeart.bat"
    exit 0
} catch {
    Write-Host ("Ошибка установки: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
