"""CustomTkinter interface for Word by Heart.

Layout and appearance values live in ``THEME`` so the visual design can be
adjusted without touching the analysis workflow below.
"""

import logging
import os
import queue
import subprocess
import sys
import tkinter as tk
import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from pydantic import ValidationError

from src.config import load_config
from src.gui.configuration import LANGUAGES, build_config, save_config
from src.gui.controller import Controller
from src.gui.secrets import load_key, save_key
from src.languages.installation import language_is_installed


# Все основные настройки внешнего вида собраны здесь. Меняйте палитру, шрифт,
# размеры окна и элементов здесь, чтобы не искать значения по всему файлу.
THEME = {
    "most_dark": "#181d23",
    "dark": "#272f3a",
    "medium": "#3c4759",
    "light": "#596680",
    "white": "#ffffff",
    "gray": "#c3c3c3",
    "font": "Roboto Condensed",
    "font_semibold": "Roboto Condensed SemiBold",
    "font_size": 18,
    "title_size": 36,
    "border": 2,
    "radius": 8,
    "mini_radius": 8,
    "window_width": 572,
    "window_height": 652,
    "pad_x": 20,
    "button_height": 32,
    "control_height": 32,
    "upper_button_width": 134,
    "extended_button_width": 82,
}


def open_path(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _font(family=None, size=None, weight="normal"):
    """Use the bundled Roboto Condensed face with a safe Tk fallback."""
    family = family or THEME["font"]
    size = size or THEME["font_size"]
    return (family, size, weight)


def _register_fonts(window):
    # Подключает Roboto Condensed для текущего процесса Windows; установка не нужна.
    if os.name != "nt":
        return
    try:
        import ctypes

        fonts = Path(__file__).resolve().parents[1] / "fonts" / "Roboto_Condensed" / "static"
        files = (fonts / "RobotoCondensed-Regular.ttf", fonts / "RobotoCondensed-SemiBold.ttf")
        if not all(path.is_file() for path in files):
            return
        gdi = ctypes.windll.gdi32
        for path in files:
            gdi.AddFontResourceExW(str(path), 0x10, 0)
        window._registered_font_files = files
    except (OSError, AttributeError):
        # Tk will use its platform sans-serif font if private font registration fails.
        return


def _enable_entry_editing(entry):
    """Add layout-independent clipboard shortcuts and a context menu."""
    target = getattr(entry, "_entry", entry)

    def focus_input(_event=None):
        # Borderless Windows dialogs may not activate on a normal focus_set.
        target.focus_force()

    def virtual_event(name):
        focus_input()
        target.event_generate(name)

    def select_all():
        target.select_range(0, tk.END)
        target.icursor(tk.END)

    def keyboard_shortcut(event):
        # Windows keycodes stay the same when the user switches keyboard layout.
        action = {
            65: select_all,
            67: lambda: virtual_event("<<Copy>>"),
            86: lambda: virtual_event("<<Paste>>"),
            88: lambda: virtual_event("<<Cut>>"),
        }.get(event.keycode)
        if action is None:
            return None
        action()
        return "break"

    menu = tk.Menu(entry, tearoff=False)
    menu.add_command(label="Вырезать", command=lambda: virtual_event("<<Cut>>"))
    menu.add_command(label="Копировать", command=lambda: virtual_event("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: virtual_event("<<Paste>>"))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=select_all)

    def show_menu(event):
        focus_input()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def paste(_event=None):
        virtual_event("<<Paste>>")
        return "break"

    target.bind("<Control-KeyPress>", keyboard_shortcut, add="+")
    target.bind("<Button-1>", focus_input, add="+")
    # CTkEntry's background/border is a separate canvas, outside the Tk Entry.
    canvas = getattr(entry, "_canvas", None)
    if canvas is not None:
        canvas.bind("<Button-1>", focus_input, add="+")
        canvas.bind("<Button-3>", show_menu, add="+")
    target.bind("<Shift-Insert>", paste, add="+")
    target.bind("<Button-3>", show_menu, add="+")
    entry._editing_menu = menu


def _focus_dialog_entry(window, entry):
    """Focus the input after the borderless dialog has been mapped."""
    def focus():
        if window.winfo_exists() and entry.winfo_exists() and window.winfo_viewable():
            entry.focus_force()

    def mapped(event):
        if event.widget == window:
            window.after_idle(focus)

    window.bind("<Map>", mapped, add="+")
    window.after_idle(focus)


class Tooltip:
    """Универсальная подсказка с задержкой для элемента управления и его подписи."""

    def __init__(self, widgets, text, delay=450):
        self.widgets = [widgets] if not isinstance(widgets, (tuple, list)) else list(widgets)
        self.text, self.delay = text, delay
        self.timer = None
        self._timer_widget = None
        self.window = None
        for widget in self.widgets:
            widget.bind("<Enter>", self._schedule, add="+")
            widget.bind("<Leave>", self._hide, add="+")
            widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._cancel_timer()
        widget = event.widget if event else self.widgets[0]
        self._timer_widget = widget
        self.timer = widget.after(self.delay, lambda: self._show(widget))

    def _show(self, widget):
        self.timer = None
        self._timer_widget = None
        if self.window or not widget.winfo_exists():
            return
        self.window = tk.Toplevel(widget)
        self.window.wm_overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=THEME["most_dark"])
        label = tk.Label(
            self.window, text=self.text, bg=THEME["dark"], fg=THEME["white"],
            font=_font(size=14), justify="left", wraplength=330,
            padx=10, pady=7, relief="solid", bd=1,
        )
        label.pack(padx=1, pady=1)
        x, y = widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height() + 5
        self.window.geometry(f"+{x}+{y}")

    def _cancel_timer(self):
        if self.timer:
            try:
                self._timer_widget.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
            self._timer_widget = None

    def _hide(self, _event=None):
        self._cancel_timer()
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class MainWindow(ctk.CTk):
    def __init__(self, root):
        super().__init__()
        _register_fonts(self)
        self.root, self.controller, self.files = root, Controller(), {}
        self.controls = []
        self._help_window = None
        self._api_key_window = None
        self._language_install_window = None
        self._language_install_process = None
        self._closing = False
        self._poll_id = None
        self._progress = None
        self._progress_second = None
        # Размер, системные свойства и общий фон главного окна.
        self.title("Word by Heart")
        self.geometry(f"{THEME['window_width']}x{THEME['window_height']}")
        self.resizable(False, False)
        self.configure(
            fg_color=THEME["most_dark"],
            highlightthickness=3,
            highlightbackground=THEME["most_dark"],
            highlightcolor=THEME["most_dark"],
        )
        self.tk.call(
            self._w,
            "configure",
            "-highlightthickness", 3,
            "-highlightbackground", THEME["most_dark"],
            "-highlightcolor", THEME["most_dark"],
        )
        self._set_window_icon()
        self.overrideredirect(True)
        self.bind("<Map>", self._main_window_mapped, add="+")
        self.after_idle(self._sync_taskbar)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.configure(fg_color=THEME["medium"])
        # Верхняя панель: логотип, название и кнопки свернуть/закрыть.
        self._build_titlebar()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        body = ctk.CTkFrame(self, fg_color=THEME["medium"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=THEME["pad_x"], pady=(4, 0))
        body.grid_columnconfigure(1, weight=1)

        # Номера строк основной сетки body:
        # 0 — заголовок; 1 — справка; 2 — выбор файла; 3 — язык;
        # 4–5 — флажки; 7 — расширенные параметры;
        # 8 — запуск анализа; 9 — кнопки результатов.
        # Заголовок приложения и строка справки.
        ctk.CTkLabel(body, text="Word by Heart", font=_font(THEME["font_semibold"], THEME["title_size"]), text_color=THEME["white"]).grid(
            row=0, column=0, columnspan=3, pady=(4, 10)
        )
        help_button = self._button(body, "Справка", self.show_help, width=THEME["upper_button_width"])
        help_button.grid(row=1, column=0, sticky="w", pady=(5, 5))
        ctk.CTkLabel(body, text="Описание и инструкция по работе с приложением", font=_font(), text_color=THEME["white"]).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(16, 0)
        )

        # Выбор TXT-файла: кнопка, поле с путём и выпадающий список языка.
        browse = self._button(body, "Выберите файл", self.browse, width=THEME["upper_button_width"])
        browse.grid(row=2, column=0, sticky="w", pady=(5, 5))
        self.source = ctk.StringVar()
        self.source_path = None
        self._setting_source = False
        self.source.trace_add("write", self._source_text_changed)
        self.file_entry = ctk.CTkEntry(body, textvariable=self.source, height=THEME["control_height"],
                                       fg_color=THEME["light"], border_color=THEME["most_dark"],
                                       border_width=THEME["border"], corner_radius=THEME["radius"],
                                       text_color=THEME["white"], font=_font())
        self.file_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=(5, 5))
        self.controls += [self.file_entry, browse]
        self._set_source_path(self.root / "data" / "input" / "demo_en.txt")
        self.language = ctk.StringVar(value="English")
        self._previous_language = "English"
        language_frame = ctk.CTkFrame(
            body,
            fg_color=THEME["most_dark"],
            border_width=THEME["border"],
            border_color=THEME["most_dark"],
            corner_radius=THEME["radius"],
        )
        language_frame.grid(row=3, column=0, sticky="w", pady=(5, 5))
        language = ctk.CTkOptionMenu(language_frame, width=THEME["upper_button_width"]-4, values=list(LANGUAGES), variable=self.language,
                                     command=self.language_changed, height=THEME["control_height"]-4,
                                     fg_color=THEME["dark"], button_color=THEME["dark"],
                                     button_hover_color=THEME["light"], text_color=THEME["white"],
                                     font=_font(), dropdown_fg_color=THEME["dark"],
                                     dropdown_text_color=THEME["white"], corner_radius=THEME["radius"]-2)
        language.grid(row=0, column=0, padx=2, pady=2)
        self.language_menu = language
        self._lang_tip_label = ctk.CTkLabel(body, text="Язык текста", font=_font(), text_color=THEME["white"])
        self._lang_tip_label.grid(row=3, column=1, sticky="w", padx=16)
        self.controls.append(language)

        # Основные параметры анализа: перевод LLM и исключение известных слов.
        self.cards, self.machine, self.known, self.ipa = [ctk.BooleanVar() for _ in range(4)]
        self._check(body, 4, " Перевод через LLM", self.machine, self.translation_changed,
                    "Для перевода через LLM нужен OpenAI API key. Введите API key. Он будет сохранен в .local/api-key.bin")
        self._check(body, 5, " Исключить известные слова", self.known, None,
                    "Известные слова не будут включаться в итоговый список слов и в карточки для изучения")
        self.key = ctk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        if not self.key.get():
            try:
                self.key.set(load_key(root))
            except OSError:
                logging.getLogger(__name__).warning("Saved API key could not be decrypted for this account")

        # Блок расширенных параметров: три значения и связанные с ними подсказки.
        self.expanded = True
        self.advanced = ctk.CTkFrame(body, fg_color=THEME["dark"], border_color=THEME["most_dark"],
                                     border_width=THEME["border"], corner_radius=THEME["radius"])
        self.advanced.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(5, 5))
        self.advanced.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.advanced, text="Расширенные настройки", font=_font(THEME["font_semibold"]),
                     text_color=THEME["white"]).grid(row=0, column=0, columnspan=2, pady=(5, 3))
        self.coverage, self.specificity, self.occurrences = [ctk.StringVar() for _ in range(3)]
        settings = (
            ("Покрытие текста, %", self.coverage, "Определяет долю текста, которую должны покрывать отобранные наиболее частотные слова"),
            ("Порог специфичности", self.specificity, "Во сколько раз слово встречается в анализируемом тексте чаще, чем в других текстах"),
            ("Минимум вхождений в тексте", self.occurrences, "Минимальное количество раз, которое слово должно встретиться в тексте, чтобы оно попало в словарь"),
        )
        for row, (label, variable, tip) in enumerate(settings, 1):
            last_row = row == len(settings)
            row_padding = (3, 10) if last_row else (3, 3)
            label_widget = ctk.CTkLabel(self.advanced, text=label, font=_font(), text_color=THEME["white"])
            label_widget.grid(row=row, column=1, sticky="w", padx=(14, 8), pady=row_padding)
            entry = ctk.CTkEntry(self.advanced, textvariable=variable, width=THEME["extended_button_width"], height=THEME["button_height"], font=_font(),
                                 fg_color=THEME["light"], border_color=THEME["most_dark"], border_width=THEME["border"],
                                 text_color=THEME["white"], corner_radius=THEME["radius"], justify="center")
            entry.grid(row=row, column=0, padx=(14, 0), pady=row_padding)
            Tooltip([label_widget, entry], tip)
            self.controls.append(entry)
        # Чекбокс IPA оставлен подготовленным для размещения в блоке настроек.
        #ipa = ctk.CTkCheckBox(self.advanced, text="Добавить транскрипцию IPA", variable=self.ipa,
        #                      font=_font(size=13), fg_color=THEME["dark"], hover_color=THEME["light"],
        #                      border_color=THEME["most_dark"], checkmark_color=THEME["white"])
        #ipa.grid(row=4, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 8))
        #self.controls.append(ipa)
        # Кнопка запуска анализа и поясняющая подсказка.
        self.start_button = ctk.CTkButton(body, text="Начать анализ", height=THEME["button_height"],
                                          font=_font(), command=self.start, fg_color=THEME["light"],
                                          hover_color=THEME["dark"], border_color=THEME["most_dark"],
                                          border_width=THEME["border"], corner_radius=THEME["radius"], text_color=THEME["white"])
        self.start_button.grid(row=8, column=0, columnspan=3, pady=(14, 7))
        self.controls.append(self.start_button)
        Tooltip(self.start_button, "Запускает анализ текста. В результате будут сформированы список слов и карточки для изучения")

        # Четыре кнопки открытия созданных результатов.
        results = ctk.CTkFrame(body, fg_color="transparent")
        results.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        results.grid_columnconfigure(0, weight=1, uniform="result")
        results.grid_columnconfigure(1, weight=1, uniform="result")
        self.result_buttons = {}
        result_defs = (("list", "Открыть список слов"), ("table", "Сводная таблица"),
                       ("cards", "Открыть карточки"), ("folder", "Папка с результатами"))
        for index, (key, label) in enumerate(result_defs):
            button = self._button(results, label, lambda name=key: self.open_result(name), state="disabled")
            button.configure(text_color_disabled=THEME["gray"])
            button.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0, 5) if index % 2 == 0 else (5, 0),
                pady=5,
            )
            self.result_buttons[key] = button
        # Нижняя строка показывает ход анализа, завершение или текст ошибки.
        self.status_separator = ctk.CTkFrame(
            self,
            fg_color=THEME["most_dark"],
            height=2,
            border_width=0,
            corner_radius=0,
        )
        self.status_separator.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        self.status_separator.grid_propagate(False)

        self.status_frame = ctk.CTkFrame(self, fg_color=THEME["dark"], border_width=0, corner_radius=0)
        self.status_frame.grid(row=3, column=0, sticky="ew", padx=0, pady=0)
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(self.status_frame, text="Статус: Настройка параметров анализа", anchor="w",
                                    font=_font(size=THEME["font_size"]), text_color=THEME["white"],
                                    fg_color=THEME["dark"], corner_radius=0, height=30)
        self.status.grid(row=0, column=0, sticky="ew", padx=7)
        self.defaults()
        self._poll_id = self.after(100, self.poll)

        Tooltip(browse, "Выберите txt-файл с текстом на иностранном языке")
        # Подсказка привязана только к подписи: она не перекрывает открытое меню языка.
        Tooltip(self._lang_tip_label, "Выберите язык, на котором написан текст")

    def _build_titlebar(self):
        # Самодельная верхняя строка нужна для оформления в цветах приложения.
        bar = tk.Frame(self, bg=THEME["most_dark"], height=32)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)
        logo_path = Path(__file__).resolve().parents[1] / "logo" / "logo16x16.png"
        try:
            self._logo = tk.PhotoImage(file=str(logo_path))
            tk.Label(bar, image=self._logo, bg=THEME["most_dark"]).grid(row=0, column=0, padx=(9, 5))
        except (tk.TclError, OSError):
            pass
        tk.Label(bar, text="Word by Heart", bg=THEME["most_dark"], fg=THEME["white"],
                 font=(THEME["font"], 12)).grid(row=0, column=1, sticky="w")
        for col, (symbol, command) in enumerate((("–", self._minimize), ("×", self.close)), 2):
            button = tk.Label(bar, text=symbol, bg=THEME["most_dark"], fg=THEME["white"],
                              font=("Segoe UI", 14), width=4, cursor="hand2", anchor="n",)
            button.grid(row=0, column=col, sticky="nsew")
            button.bind("<Button-1>", lambda _event, fn=command: fn())
            button.bind("<Enter>", lambda event: event.widget.configure(bg=THEME["dark"]))
            button.bind("<Leave>", lambda event: event.widget.configure(bg=THEME["most_dark"]))
        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)
        self._titlebar = bar

    def _set_window_icon(self):
        """Use the bundled logo for the taskbar and other Windows window UI."""
        logo_path = Path(__file__).resolve().parents[1] / "logo" / "logo16x16.png"
        try:
            self._taskbar_icon = tk.PhotoImage(file=str(logo_path))
            self.iconphoto(True, self._taskbar_icon)
        except (tk.TclError, OSError):
            logging.getLogger(__name__).warning("Application icon could not be loaded: %s", logo_path)

    def _windows_set_titlebar_icon(self):
        # CTk schedules this hook after startup; retain our PNG instead of its ICO.
        self._set_window_icon()

    def _main_window_mapped(self, event):
        if event.widget is self and not self._closing:
            self.after_idle(self._sync_taskbar)

    def _sync_taskbar(self):
        if os.name != "nt" or self._closing:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetAncestor.restype = wintypes.HWND
            user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongW.restype = wintypes.LONG
            user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            user32.SetWindowLongW.restype = wintypes.LONG
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow.restype = wintypes.BOOL
            hwnd = user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT: Tk's native wrapper
            style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            app_style = (style | 0x00040000) & ~0x00000080  # APPWINDOW, not TOOLWINDOW
            if style != app_style:
                ctypes.set_last_error(0)
                previous = user32.SetWindowLongW(hwnd, -20, app_style)
                if not previous and ctypes.get_last_error():
                    raise ctypes.WinError(ctypes.get_last_error())
                if self.state() == "normal":
                    # Shell refresh is required after changing taskbar styles.
                    user32.ShowWindow(hwnd, 0)
                    user32.ShowWindow(hwnd, 4)  # show without stealing focus
            self._set_window_icon()
        except (OSError, tk.TclError):
            logging.getLogger(__name__).exception("Unable to update Windows taskbar")

    def _drag_start(self, event):
        self._drag_x, self._drag_y = event.x_root - self.winfo_x(), event.y_root - self.winfo_y()

    def _drag_move(self, event):
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _minimize(self):
        """Temporarily restore native decorations so Windows can minimize the window."""
        self.overrideredirect(False)
        self.iconify()
        self._restore_map_id = self.bind("<Map>", self._restore_borderless, add="+")

    def _restore_borderless(self, _event=None):
        if _event is not None and _event.widget is not self:
            return
        if self.state() == "normal":
            self.overrideredirect(True)
            self.unbind("<Map>", self._restore_map_id)
            self.after_idle(self._sync_taskbar)

    def _button(self, parent, text, command, **kwargs):
        # Общий конструктор кнопок: единая рамка, цвет, шрифт и скругление.
        return ctk.CTkButton(parent, text=text, command=command, height=kwargs.pop("height", THEME["button_height"]),
                             fg_color=THEME["dark"], hover_color=THEME["light"], text_color=THEME["white"],
                             border_color=THEME["most_dark"], border_width=THEME["border"],
                             corner_radius=THEME["radius"], font=_font(), **kwargs)

    def _check(self, parent, row, label, variable, command, tip):
        # Общий конструктор чекбоксов; tip задаёт текст подсказки.
        widget = ctk.CTkCheckBox(parent, text=label, variable=variable, command=command, font=_font(),
                                 fg_color=THEME["dark"], hover_color=THEME["light"],
                                 border_color=THEME["most_dark"], border_width=THEME["border"],
                                 corner_radius=THEME["mini_radius"],
                                 checkmark_color=THEME["white"], text_color=THEME["white"])
        widget.grid(row=row, column=0, columnspan=3, sticky="w", pady=(5, 5))
        Tooltip(widget, tip)
        self.controls.append(widget)
        return widget

    def _dialog_body(self, window, title, close_command):
        """Give a secondary window the same border and title bar as the main window."""
        window.configure(fg_color=THEME["medium"])
        window.tk.call(
            window._w, "configure",
            "-highlightthickness", 3,
            "-highlightbackground", THEME["most_dark"],
            "-highlightcolor", THEME["most_dark"],
        )
        window.overrideredirect(True)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)

        bar = tk.Frame(window, bg=THEME["most_dark"], height=32)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)
        if hasattr(self, "_logo"):
            tk.Label(bar, image=self._logo, bg=THEME["most_dark"]).grid(row=0, column=0, padx=(9, 5))
        tk.Label(bar, text=title, bg=THEME["most_dark"], fg=THEME["white"],
                 font=(THEME["font"], 12)).grid(row=0, column=1, sticky="w")

        def restore_borderless(_event=None):
            if window.state() == "normal":
                window.overrideredirect(True)
                window.unbind("<Map>")

        def minimize():
            window.overrideredirect(False)
            window.iconify()
            window.bind("<Map>", restore_borderless, add="+")

        for col, (symbol, command) in enumerate((("–", minimize), ("×", close_command)), 2):
            button = tk.Label(bar, text=symbol, bg=THEME["most_dark"], fg=THEME["white"],
                              font=("Segoe UI", 14), width=4, cursor="hand2", anchor="n")
            button.grid(row=0, column=col, sticky="nsew")
            button.bind("<Button-1>", lambda _event, fn=command: fn())
            button.bind("<Enter>", lambda event: event.widget.configure(bg=THEME["dark"]))
            button.bind("<Leave>", lambda event: event.widget.configure(bg=THEME["most_dark"]))

        def drag_start(event):
            window._drag_x = event.x_root - window.winfo_x()
            window._drag_y = event.y_root - window.winfo_y()

        def drag_move(event):
            window.geometry(f"+{event.x_root - window._drag_x}+{event.y_root - window._drag_y}")

        bar.bind("<ButtonPress-1>", drag_start)
        bar.bind("<B1-Motion>", drag_move)

        body = ctk.CTkFrame(window, fg_color=THEME["medium"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        return body

    def _center_dialog(self, window):
        """Place a secondary window over the center of the main window."""
        window.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - window.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - window.winfo_height()) // 2
        window.geometry(f"+{max(0, x)}+{max(0, y)}")

    def show_help(self):
        # Создаёт отдельное окно справки; повторное нажатие поднимает уже открытое.
        if self._help_window and self._help_window.winfo_exists():
            self._help_window.deiconify()
            self._help_window.lift()
            return
        win = ctk.CTkToplevel(self)
        self._help_window = win
        win.title("Справка — Word by Heart")
        win.geometry("760x520")
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        body = self._dialog_body(win, "Справка — Word by Heart", win.destroy)
        ctk.CTkLabel(body, text="Справка", font=_font(THEME["font_semibold"], 21), text_color=THEME["white"]).pack(padx=20, pady=(18, 8))
        text = """        Word by Heart – это приложение для подготовки лексики к изучению, необходимой для прочтения конкретной книги или просмотра сериала на иностранном языке.
        Приложение создает из текста готовый набор слов для изучения и повторения.
        

        Краткая инструкция 

        1. Выберите txt-файл (для тестового запуска уже выбран файл demo_en.txt)
        2. Нажмите «Начать анализ».
        3. Откройте «Список слов», «Карточки», «Сводную таблицу» и «Папку с результатами»

        Список слов – это слова, которые нужно выучить, для комфортного чтения книги на иностранном языке.

        Карточки – это слова из списка, размещенные на листе в таблице 8х3. Один лист содержит 24 карточки. Файл подготовлен для двусторонней печати. Сначала распечатайте лицевые стороны всех листов, затем переверните бумагу и распечатайте обратные стороны. После разрезания получатся двусторонние карточки для изучения и повторения слов.

        Сводная таблица содержит леммы и словоформы, распознанные программой в тексте, а также их частоту, переводы, транскрипцию, грамматическую информацию и примечания. Она удобна для дополнительного анализа текста. 

        В папке с результатами хранятся все результирующие файлы.
        

        Подробная инструкция

        1. Выберите txt-файл с текстом на иностранном языке. Рекомендуется использовать кодировку UTF-8. Программа пытается автоматически распознать и прочитать другие распространённые кодировки, однако в некоторых случаях возможны ошибки. Если текст отображается неправильно, откройте файл в Блокноте, выберите «Сохранить как» и укажите кодировку UTF-8.

        2. Выберите язык, на котором написан текст. Сейчас приложение поддерживает английский и испанский языки.

        3. По умолчанию перевод слов выполняется через локальный словарь Kaikki. При необходимости можно включить перевод через языковую модель (LLM). Для этого потребуется API key OpenAI.

        4. Если у вас имеется список слов, которые вы уже знаете, перенесите их в словарь (my_dictionary_en.xlsx – для английского, my_dictionary_es.xlsx – для испанского), который находится в корневой папке приложения. Для примера в словари уже внесены несколько слов. 
        Если слово из вашего словаря будет найдено в книге, оно не будет переводиться и не будет включаться в итоговые списки и карточки слов для изучения. При этом такие слова останутся в сводной таблице.

        5. Расширенные настройки. Установите ограничения для выбора слов параметрами «Покрытие текста», «Порог специфичности» и «Минимум вхождений в тексте».
        по умолчанию заданы следующие параметры:
        
        Покрытие текста – 90%. В список для изучения войдут наиболее частые слова, которые суммарно покрывают 90% текста.
        
        Порог специфичности – 20. Дополнительно в список войдут слова, которые не входят в диапазон покрытия текста, но встречаются в тексте в 20 и более раз чаще, чем в среднем в других текстах. Такие слова, по идее, должны быть «важными» именно для данного текста и отражать стиль автора и особенность произведения.
        
        Минимум вхождений в тексте – 4. Слово должно встретиться в тексте не менее четырёх раз, чтобы попасть в список для изучения, даже если оно соответствует настройкам покрытия или специфичности.

        6. Нажмите «Начать анализ». Обработка текста зависит от его размера и выбранного способа перевода. При переводе через Kaikki она обычно занимает несколько минут. Перевод через LLM может занять существенно больше времени, особенно для большой книги.

        7. Изучите результат анализа.


        Описание работы приложения

        После выбора текста на иностранном языке программа выполняет обработку текста в несколько этапов.

        Предобработка. Исходный текст загружается, очищается и подготавливается к анализу. Длинный текст разбивается на небольшие фрагменты (чанки), чтобы программа могла корректно обработать даже большую книгу.

        NLP-анализ. Для проведения NLP-анализа используется модель spaCy. Она выделяет предложения, слова, начальные формы слов (леммы), части речи и грамматические признаки.

        Частотный анализ. Программа собирает леммы, словоформы, примеры использования слов, подсчитывает частоту слов и их покрытие текста.

        Оценка полезности слова. Частота слова в данном тексте сравнивается с его обычной частотой в языке. В качестве источника общеязыковой частотности используется библиотека wordfreq, основанная на больших массивах текстов. Параметр «специфичность» показывает, насколько чаще слово встречается в этом тексте по сравнению с его обычной частотой в языке. Это помогает выделить слова, особенно важные для конкретного текста.

        Постобработка текста. Программа очищает и объединяет результаты анализа, чтобы слова отображались в удобном для изучения виде. 

        Грамматическое дополнение. Программа добавляет сведения, полезные для изучения слов. Для английского языка, к примеру, добавляются основные формы существительных и глаголов. Для этого используются данные языковой модели, правила программы и словарь исключений.

        Транскрипция (IPA). Для создания транскрипций используется eSpeak NG.

        Перевод. Перевод слов по умолчанию выполняется через локальный словарь Kaikki. Имеется возможность подключить перевод через LLM. При использовании LLM в модель передаётся не только слово, но и примеры его использования в тексте, часть речи и словоформы. Это позволяет переводить слова с учётом контекста.

        Тестирование перевода через LLM проводилось на модели OpenAI GPT-5.6 Luna.

        Валидация результата. Программа проверяет результаты обработки и отмечает возможные проблемы. Например, если программа находит отсутствующий перевод или транскрипцию, сомнительную форму слова, неоднозначность или ошибку автоматического анализа, то такие слова попадают в отдельный список для проверки.

        Подготовка результатов. Программа создаёт итоговые таблицы со словарём, переводами, транскрипцией и грамматической информацией, а также список слов и карточки для изучения.


        Описание идеи

        Проект вырос из практической методики, где вместо абстрактной цели «выучить язык» ставится конкретная задача - прочитать книгу или посмотреть сериал.
        Изучение ограниченного набора слов, которые действительно важны для понимания выбранного текста, позволяет быстрее перейти к контенту на иностранном языке.
        Чтение любимых книг и просмотр сериалов в оригинале приносят удовольствие, дают ощущение прогресса и поддерживают мотивацию к дальнейшему изучению языка.
"""
        textbox = ctk.CTkTextbox(body, wrap="word", font=_font(), fg_color=THEME["dark"], text_color=THEME["white"],
                                 border_color=THEME["most_dark"], border_width=THEME["border"], corner_radius=THEME["radius"])
        textbox.pack(fill="both", expand=True, padx=18, pady=(4, 18))
        textbox.insert("1.0", text)
        textbox.configure(state="disabled")
        self._center_dialog(win)

    def defaults(self, *_):
        # Загружает начальные настройки из YAML-файла выбранного языка.
        cfg = load_config(self.root / "config" / f"demo_{LANGUAGES[self.language.get()]}.yaml")
        self.cards.set(cfg.cards.enabled)
        self.machine.set(cfg.machine_translation.enabled)
        self.known.set(cfg.known_dictionary.enabled)
        self.ipa.set(cfg.pronunciation.enabled)
        self.coverage.set(str(cfg.translation.cumulative_coverage_limit))
        self.specificity.set(str(cfg.translation.specificity_threshold))
        self.occurrences.set(str(cfg.translation.min_book_occurrences))
        self.translation_changed()

    def language_changed(self, selected):
        language = LANGUAGES[selected]
        if language == "es" and not language_is_installed(self.root, language):
            self.show_language_install_window()
            return
        self._previous_language = selected
        self.defaults()

    def show_language_install_window(self):
        if self._language_install_window and self._language_install_window.winfo_exists():
            self._language_install_window.deiconify()
            self._language_install_window.lift()
            return

        win = ctk.CTkToplevel(self)
        self._language_install_window = win
        win.title("Установка испанского языка")
        win.geometry("560x230")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        def cancel():
            self.language.set(self._previous_language)
            win.destroy()

        body = self._dialog_body(win, "Установка испанского языка", cancel)
        ctk.CTkLabel(
            body,
            text="Для создания списка слов для испанского языка необходимо установить дополнительные библиотеки",
            font=_font(size=18), text_color=THEME["white"], justify="left", wraplength=510,
        ).pack(fill="x", padx=24, pady=(30, 20))

        def install():
            win.grab_release()
            win.destroy()
            self._start_spanish_installation()

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=(0, 20))
        self._button(buttons, "Отмена", cancel).pack(side="left")
        self._button(buttons, "Установить испанский", install).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", cancel)
        self._center_dialog(win)

    def _start_spanish_installation(self):
        installer = self.root / "INSTALL_SPANISH.bat"
        try:
            self._language_install_process = subprocess.Popen(
                ["cmd.exe", "/c", str(installer)],
                cwd=self.root,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            )
        except OSError:
            self.language.set(self._previous_language)
            messagebox.showerror("Установка испанского", "Не удалось запустить установку.", parent=self)
            return
        self.language_menu.configure(state="disabled")
        self.status.configure(text="Статус: Установка компонентов испанского языка…")
        self.after(500, self._poll_spanish_installation)

    def _poll_spanish_installation(self):
        if self._closing:
            return
        result = self._language_install_process.poll()
        if result is None:
            self.after(500, self._poll_spanish_installation)
            return
        self.language_menu.configure(state="normal")
        self._language_install_process = None
        if result == 0 and language_is_installed(self.root, "es"):
            self._previous_language = "Español"
            self.defaults()
            self.status.configure(text="Статус: Испанский язык установлен")
            return
        self.language.set(self._previous_language)
        self.defaults()
        self.status.configure(text="Статус: Испанский язык не установлен")
        messagebox.showerror(
            "Установка испанского",
            "Не удалось установить дополнительные компоненты. Подробности сохранены в logs/setup.log.",
            parent=self,
        )

    def translation_changed(self):
        # Запрашивает и сохраняет ключ в отдельном окне только при его отсутствии.
        if self.machine.get() and not self.key.get().strip():
            self.show_api_key_window()

    def show_api_key_window(self):
        if self._api_key_window and self._api_key_window.winfo_exists():
            self._api_key_window.deiconify()
            self._api_key_window.lift()
            self._api_key_window._api_key_entry.focus_force()
            return

        win = ctk.CTkToplevel(self)
        self._api_key_window = win
        win.title("OpenAI API key")
        win.geometry("520x264")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        def cancel():
            self.machine.set(False)
            win.destroy()

        body = self._dialog_body(win, "OpenAI API key", cancel)

        entered_key = ctk.StringVar()
        ctk.CTkLabel(body, text="Введите OpenAI API key", font=_font(THEME["font_semibold"], 21),
                     text_color=THEME["white"]).pack(padx=20, pady=(20, 10))
        entry = ctk.CTkEntry(body, textvariable=entered_key, show="*", placeholder_text="OpenAI API key",
                             height=THEME["control_height"], font=_font(), fg_color=THEME["light"],
                             border_color=THEME["most_dark"], border_width=THEME["border"],
                             corner_radius=THEME["radius"])
        entry.pack(fill="x", padx=20)
        win._api_key_entry = entry
        _enable_entry_editing(entry)
        key_path = self.root / ".local" / "api-key.bin"
        ctk.CTkLabel(
            body,
            text=f"Ключ будет сохранён в:\n{key_path}",
            font=_font(size=16), text_color=THEME["white"], justify="center", wraplength=480,
        ).pack(fill="x", padx=20, pady=(12, 10))

        def save():
            key = entered_key.get().strip()
            if not key:
                messagebox.showinfo("OpenAI API", "Введите API key.", parent=win)
                return
            try:
                save_key(self.root, key)
            except OSError:
                logging.getLogger(__name__).exception("Unable to save API key")
                messagebox.showerror("OpenAI API", "Не удалось сохранить API key.", parent=win)
                return
            self.key.set(key)
            os.environ["OPENAI_API_KEY"] = key
            win.destroy()

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(4, 16))
        self._button(buttons, "Отмена", cancel).pack(side="left")
        self._button(buttons, "Сохранить", save).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", cancel)
        entry.bind("<Return>", lambda _event: save())
        self._center_dialog(win)
        _focus_dialog_entry(win, entry)

    def browse(self):
        # Открывает системный диалог выбора входного TXT-файла.
        path = filedialog.askopenfilename(
            parent=self,
            title="Выберите текст книги",
            initialdir=self.root / "data" / "input",
            filetypes=[("Текстовые файлы", "*.txt")],
        )
        if path:
            self._set_source_path(path)

    def _set_source_path(self, path):
        path = Path(path).resolve()
        input_dir = (self.root / "data" / "input").resolve()
        try:
            path.relative_to(input_dir)
            display = path.name
        except ValueError:
            display = str(path)
        self.source_path = path
        self._setting_source = True
        self.source.set(display)
        self._setting_source = False
        self._show_ready_status()

    def _source_text_changed(self, *_):
        if not self._setting_source:
            self.source_path = None
            self._show_ready_status()

    def _show_ready_status(self):
        if hasattr(self, "status") and not self.controller.running:
            self.status.configure(text="Статус: Настройка параметров анализа")

    def set_busy(self, busy):
        for widget in self.controls:
            widget.configure(state="disabled" if busy else "normal")

    def start(self):
        # Проверяет параметры, сохраняет конфигурацию и запускает контроллер анализа.
        if self.controller.running:
            return
        try:
            if self.machine.get() and not self.key.get().strip():
                messagebox.showinfo("OpenAI API", "Введите API key или отключите перевод через модель.", parent=self)
                return
            options = {"cards": self.cards.get(), "machine": self.machine.get(), "known": self.known.get(),
                       "ipa": self.ipa.get(), "coverage": self.coverage.get().replace(",", "."),
                       "specificity": self.specificity.get().replace(",", "."), "occurrences": self.occurrences.get()}
            source, path, cfg = build_config(
                self.root,
                self.source_path or self.source.get(),
                LANGUAGES[self.language.get()],
                options,
            )
            key = self.key.get().strip() if self.machine.get() else ""
            if key:
                os.environ["OPENAI_API_KEY"] = key
            save_config(path, cfg)
            self.controller.start(self.root, path, source, key)
        except ValidationError:
            messagebox.showerror("Настройки", "Покрытие: больше 0 и не более 100%. Порог: от 0. Количество вхождений: целое число от 1.", parent=self)
            return
        except (ValueError, OSError) as exc:
            logging.getLogger(__name__).exception("Unable to start analysis")
            messagebox.showerror("Не удалось начать", str(exc) if isinstance(exc, ValueError) else "Не удалось открыть или сохранить файл. Проверьте права доступа.", parent=self)
            return
        self.files = {}
        for button in self.result_buttons.values():
            button.configure(state="disabled")
        self.set_busy(True)
        self._progress = None
        self._progress_second = None
        self.status.configure(text="Статус: Подготовка анализа…")

    def poll(self):
        # Получает события фонового процесса и обновляет статус/кнопки результатов.
        if self._closing or not self.winfo_exists():
            return
        try:
            while True:
                event = self.controller.events.get_nowait()
                kind = event.get("type")
                if kind == "progress":
                    if not self._progress or self._progress["label"] != event["label"]:
                        self._progress = {**event, "started": time.monotonic()}
                        self._progress_second = None
                    else:
                        self._progress.update(completed=event["completed"], total=event["total"])
                    self._show_progress_status()
                elif kind in {"done", "error"}:
                    self._progress = None
                    self._progress_second = None
                    self.set_busy(False)
                    if kind == "done":
                        self.status.configure(text=f"Статус: {event['summary']}")
                        self.files = event["files"]
                        for name, button in self.result_buttons.items():
                            available = name in self.files and Path(self.files[name]).exists()
                            button.configure(state="normal" if available else "disabled")
                    else:
                        self.status.configure(text="Статус: Ошибка")
                        messagebox.showerror("Word by Heart", event["message"], parent=self)
        except queue.Empty:
            pass
        if self._progress:
            self._show_progress_status()
        if not self._closing and self.winfo_exists():
            self._poll_id = self.after(100, self.poll)

    def _show_progress_status(self):
        elapsed = int(time.monotonic() - self._progress["started"])
        if elapsed == self._progress_second:
            return
        self._progress_second = elapsed
        minutes, seconds = divmod(elapsed, 60)
        elapsed_text = f"{minutes} мин {seconds:02d} сек" if minutes else f"{seconds} сек"
        self.status.configure(
            text=(f"Статус: {self._progress['label']} · "
                  f"{self._progress['completed']} из {self._progress['total']} этапов · "
                  f"выполняется {elapsed_text}")
        )

    def open_result(self, name):
        # Открывает выбранный созданный файл или папку средствами ОС.
        try:
            open_path(self.files[name])
        except (OSError, KeyError):
            messagebox.showerror("Результаты", "Не удалось открыть результат. Проверьте, что файл существует и для него установлена программа.", parent=self)

    def close(self):
        # При закрытии останавливает анализ по запросу и отменяет периодический опрос.
        if self._closing:
            return
        if self.controller.running:
            if not messagebox.askyesno("Остановить анализ?", "Обработка ещё идёт. Остановить её и закрыть окно?", parent=self):
                return
        self._closing = True
        try:
            self.controller.stop()
        except Exception:
            logging.getLogger(__name__).exception("Unable to stop analysis on exit")
        try:
            # Cancel pending focus, tooltip, polling and CTk callbacks before teardown.
            for callback in self.tk.splitlist(self.tk.call("after", "info")):
                try:
                    # Keep each callback registered with its owning widget until
                    # destroy; cancelling via self would corrupt child bookkeeping.
                    self.tk.call("after", "cancel", callback)
                except tk.TclError:
                    pass
            self._poll_id = None
            self.destroy()
        except Exception:
            logging.getLogger(__name__).exception("GUI cleanup failed; closing native window")
            try:
                self.tk.call("destroy", ".")
            except tk.TclError:
                pass
        finally:
            self.quit()
