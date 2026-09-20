import logging
import codecs
from pathlib import Path

from charset_normalizer import from_bytes

from src.storage import atomic_path

from .normalizer import normalize

logger = logging.getLogger(__name__)


def read_text_auto(source: Path) -> tuple[str, str]:
    """Decode a TXT file and return Unicode text plus the detected source encoding."""
    data = source.read_bytes()
    for marker, encoding in (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    ):
        if data.startswith(marker):
            return data.decode(encoding), encoding
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        # Legacy English and Spanish TXT files most commonly use Windows-1252.
        try:
            return data.decode("cp1252"), "cp1252"
        except UnicodeDecodeError:
            match = from_bytes(data).best()
        if match is None:
            raise UnicodeError("Не удалось определить кодировку TXT-файла")
        return str(match), match.encoding or "unknown"


def run(source: Path, target: Path, config):
    decoded, encoding = read_text_auto(source)
    text = normalize(decoded, config)
    with atomic_path(target) as tmp:
        tmp.write_text(text, encoding="utf-8")
    logger.info("Исходный файл: %s; кодировка: %s; символов: %d", source, encoding, len(text))
