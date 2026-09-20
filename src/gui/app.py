"""python -m src.gui.app; pythonw is supported, including startup failures."""

import logging
import os
import shutil
import sys
from pathlib import Path

from src.runtime import ROOT, configure_logging, prepare_environment


def configure_windows_app_identity():
    """Give the pythonw-hosted GUI its own stable taskbar identity on Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WordByHeart.WordByHeart")
    except (AttributeError, OSError):
        logging.getLogger(__name__).warning("Windows taskbar identity could not be configured")


def configure_tk_runtime():
    """Keep Tcl/Tk scripts under the project venv for restricted Windows profiles."""
    version = "8.6"
    source = Path(sys.base_prefix) / "tcl"
    local = ROOT / ".venv" / "tcl"
    for name in (f"tcl{version}", f"tk{version}"):
        source_dir = source / name
        target_dir = local / name
        marker = "init.tcl" if name.startswith("tcl") else "tk.tcl"
        if not (target_dir / marker).is_file():
            if not (source_dir / marker).is_file():
                raise FileNotFoundError(f"Tcl/Tk runtime files are missing: {source_dir}")
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        os.environ["TCL_LIBRARY" if name.startswith("tcl") else "TK_LIBRARY"] = str(target_dir)


def main():
    handler = configure_logging()
    if sys.stderr is None:
        sys.stderr = handler.stream
    if sys.stdout is None:
        sys.stdout = handler.stream
    try:
        prepare_environment()
        configure_tk_runtime()
        configure_windows_app_identity()
        import customtkinter as ctk

        from src.gui.main_window import MainWindow

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        app = MainWindow(ROOT)

        def callback_error(exc_type, exc, tb):
            logging.getLogger(__name__).error("GUI callback failed", exc_info=(exc_type, exc, tb))
            from tkinter import messagebox

            messagebox.showerror(
                "Word by Heart",
                "Не удалось выполнить действие. Подробности: logs/wordbyheart.log.",
                parent=app,
            )

        app.report_callback_exception = callback_error
        app.mainloop()
        return 0
    except Exception:
        logging.getLogger(__name__).exception("GUI startup failed")
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                "Не удалось запустить WordByHeart. Запустите INSTALL.bat для восстановления установки.",
                "WordByHeart",
                0x10,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
