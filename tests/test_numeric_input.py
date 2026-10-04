import pytest

from src.gui.configuration import valid_numeric_edit


@pytest.mark.parametrize("value,maximum,decimal,expected", [
    ("", 100, False, True), ("0", 100, False, True), ("100", 100, False, True),
    ("90,5", 100, False, False), ("100.01", 100, False, False),
    ("abc", 100, True, False), ("12x", 100, True, False),
    ("-1", 100, True, False), ("1e2", 100, True, False),
    ("1.5", 1000, False, False), ("1000", 1000, False, True),
    ("1001", 1000, False, False), ("1000000", 1000000, False, True),
    ("1000001", 1000000, False, False),
])
def test_numeric_edit(value, maximum, decimal, expected):
    assert valid_numeric_edit(value, maximum, decimal) is expected


@pytest.mark.parametrize("maximum,decimal,minimum", [(100, False, 0), (1000, False, 0), (1000000, False, 1)])
def test_actual_entry_input_and_clipboard(maximum, decimal, minimum):
    ctk = pytest.importorskip("customtkinter")
    from src.gui.app import configure_tk_runtime

    configure_tk_runtime()
    root = ctk.CTk()
    root.withdraw()
    try:
        variable = ctk.StringVar()
        entry = ctk.CTkEntry(root, textvariable=variable)
        entry.configure(validate="key", validatecommand=(root.register(
            lambda value: valid_numeric_edit(value, maximum, decimal, minimum)), "%P"))
        variable.set(str(maximum))
        entry.delete(0, "end")
        for value in ["abc", "12x", "-1", "1e2", "90.5", "90,5", str(maximum + 1)]:
            entry.insert(0, value)
            assert entry.get() == ""
            root.clipboard_clear()
            root.clipboard_append(value)
            root.tk.eval(root.tk.call("bind", "Entry", "<<Paste>>").replace("%W", str(entry._entry)))
            assert entry.get() == ""
        for value in [str(minimum), str(maximum)]:
            entry.insert(0, value)
            assert entry.get() == value
            entry.delete(0, "end")
            root.clipboard_clear()
            root.clipboard_append(value)
            root.tk.eval(root.tk.call("bind", "Entry", "<<Paste>>").replace("%W", str(entry._entry)))
            assert entry.get() == value
            entry.delete(0, "end")
        if minimum == 1:
            entry.insert(0, "0")
            assert entry.get() == ""
    finally:
        root.destroy()


@pytest.mark.parametrize("maximum,minimum,default", [(100, 0, 90), (1000, 0, 20), (1000000, 1, 4)])
def test_empty_default_and_replacement(maximum, minimum, default):
    ctk = pytest.importorskip("customtkinter")
    from src.gui.app import configure_tk_runtime
    from src.gui.configuration import restore_empty_default

    configure_tk_runtime()
    root = ctk.CTk()
    root.withdraw()
    try:
        variable = ctk.StringVar(value=str(default))
        entry = ctk.CTkEntry(root, textvariable=variable)
        entry.configure(validate="key", validatecommand=(root.register(
            lambda value: valid_numeric_edit(value, maximum, False, minimum)), "%P"))
        restore = restore_empty_default(entry, variable, default)
        for _ in range(2):
            entry.delete(0, "end")
            root.update_idletasks()
            assert entry.get() == ""
            restore()
            assert entry.get() == str(default)
            assert entry._entry.cget("validate") == "key"
        entry.delete(0, "end")
        entry.insert(0, str(maximum))
        root.update_idletasks()
        assert entry.get() == str(maximum)
        entry.insert("end", "x")
        assert entry.get() == str(maximum)
    finally:
        root.destroy()


