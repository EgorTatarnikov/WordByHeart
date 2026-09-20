from src.config import Preprocess
from src.preprocessing.loader import read_text_auto, run


def test_loader_detects_windows_1252_and_writes_utf8(tmp_path):
    source = tmp_path / "book.txt"
    target = tmp_path / "normalized.txt"
    expected = "El niño caminó por la estación. Mañana volverá también."
    source.write_bytes(expected.encode("cp1252"))

    text, encoding = read_text_auto(source)
    assert text == expected
    assert encoding == "cp1252"

    run(source, target, Preprocess())
    assert target.read_text(encoding="utf-8") == expected + "\n"


def test_loader_accepts_utf16_bom(tmp_path):
    source = tmp_path / "book.txt"
    source.write_bytes("Hello world".encode("utf-16"))
    assert read_text_auto(source)[0] == "Hello world"
