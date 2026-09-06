import logging
from pathlib import Path

from src.storage import atomic_path

from .normalizer import normalize

logger = logging.getLogger(__name__)


def run(source: Path, target: Path, config):
    text = normalize(source.read_text(encoding="utf-8-sig"), config)
    with atomic_path(target) as tmp:
        tmp.write_text(text, encoding="utf-8")
    logger.info("Исходный файл: %s; символов: %d", source, len(text))
