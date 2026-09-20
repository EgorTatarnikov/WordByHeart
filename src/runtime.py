"""Shared environment and private diagnostic logging for CLI and GUI."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def redact(text):
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        text = text.replace(key, "[API KEY]")
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[API KEY]", text)


class PrivateFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def configure_logging(root=ROOT, level=logging.INFO):
    directory = root / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "wordbyheart.log", maxBytes=5_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(PrivateFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)
    logging.getLogger("httpx").setLevel(logging.DEBUG if level == logging.DEBUG else logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return handler


def prepare_environment(root=ROOT):
    from dotenv import load_dotenv

    load_dotenv(root / ".env")
    from src.pronunciation.discovery import configure_espeak

    configure_espeak(root=root, required=False)
