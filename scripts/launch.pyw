"""Stdlib launcher: missing imports get a native message."""
import ctypes
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.chdir(root)
try:
    from src.gui.app import main
    raise SystemExit(main())
except Exception:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, "Не удалось запустить WordByHeart. "
                                        "Запустите INSTALL.bat для восстановления установки.",
                                        "WordByHeart", 0x10)
