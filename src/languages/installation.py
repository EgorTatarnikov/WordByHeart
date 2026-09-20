"""Checks for optional language resources without loading large NLP models."""

import importlib
import importlib.util
import json
from pathlib import Path

from src.config import load_config
from src.translation.health import dictionary_is_healthy


def language_is_installed(root: Path, language: str) -> bool:
    config = load_config(root / "config" / f"demo_{language}.yaml")
    importlib.invalidate_caches()
    if importlib.util.find_spec(config.nlp.model) is None:
        return False
    cache = (root / "config" / config.paths.cache).resolve()
    metadata = cache / "kaikki" / "SOURCES.json"
    if not metadata.is_file():
        return False
    try:
        editions = set(json.loads(metadata.read_text(encoding="utf-8")).get("editions", []))
    except (OSError, ValueError):
        return False
    return (
        "ru" in editions
        and (language != "es" or "es" in editions)
        and dictionary_is_healthy(cache / "kaikki" / "dictionary.sqlite")
    )
