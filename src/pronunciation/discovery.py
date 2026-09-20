"""Locate an installed or setup-extracted eSpeak NG without user configuration."""

import os
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dll_is_compatible(path):
    try:
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                return False
            stream.seek(60)
            offset = struct.unpack("<I", stream.read(4))[0]
            stream.seek(offset)
            if stream.read(4) != b"PE\0\0":
                return False
            machine = struct.unpack("<H", stream.read(2))[0]
        return machine == (0x8664 if struct.calcsize("P") == 8 else 0x14C)
    except (OSError, struct.error):
        return False


def candidates(root=ROOT):
    library = os.environ.get("PHONEMIZER_ESPEAK_LIBRARY")
    if library:
        yield Path(library).parent
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            yield Path(base) / "eSpeak NG"
            yield Path(base) / "Programs" / "eSpeak NG"
    executable = shutil.which("espeak-ng")
    if executable:
        yield Path(executable).parent
    # Restrict recursive lookup to the app-owned extraction directory.
    local = root / ".local" / "espeak"
    if local.exists():
        yield local
        yield from (p.parent for p in local.rglob("libespeak-ng.dll"))
    if os.name == "nt":
        import winreg

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(
                        hive,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                        0,
                        winreg.KEY_READ | view,
                    ) as key:
                        for index in range(winreg.QueryInfoKey(key)[0]):
                            with winreg.OpenKey(key, winreg.EnumKey(key, index)) as item:
                                try:
                                    name = winreg.QueryValueEx(item, "DisplayName")[0]
                                    if "espeak" in name.lower():
                                        yield Path(winreg.QueryValueEx(item, "InstallLocation")[0])
                                except OSError:
                                    pass
                except OSError:
                    pass


def find_espeak(root=ROOT):
    seen = set()
    for directory in candidates(root):
        if directory in seen:
            continue
        seen.add(directory)
        library = directory / "libespeak-ng.dll"
        data = directory / "espeak-ng-data"
        explicit = os.environ.get("PHONEMIZER_ESPEAK_DATA_PATH")
        if explicit and directory == Path(os.environ.get("PHONEMIZER_ESPEAK_LIBRARY", "")).parent:
            data = Path(explicit)
        if (
            library.is_file()
            and (data / "phontab").is_file()
            and (os.name != "nt" or dll_is_compatible(library))
        ):
            return library.resolve(), data.resolve()
    return None


def configure_espeak(root=ROOT, required=True):
    if os.name != "nt":
        return None  # phonemizer uses the system shared library on Unix.
    pair = find_espeak(root)
    if pair:
        library, data = pair
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(library)
        os.environ["PHONEMIZER_ESPEAK_DATA_PATH"] = str(data)
        from phonemizer.backend.espeak.wrapper import EspeakWrapper

        EspeakWrapper.set_library(str(library))
        EspeakWrapper.set_data_path(str(data))
    elif required:
        raise RuntimeError("Не найден eSpeak NG. Запустите INSTALL.bat для восстановления установки.")
    return pair


def check_espeak():
    configure_espeak()
    from src.pronunciation.service import PhonemizerService

    for language, word in (("en-gb", "hello"), ("es", "casa")):
        if not all(PhonemizerService(language).phonemize([word])):
            raise RuntimeError("eSpeak NG вернул пустую транскрипцию. Запустите INSTALL.bat.")
