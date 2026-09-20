"""Local, part-of-speech aware lookup of explicit Kaikki translations."""

import logging
import sqlite3
import unicodedata
from contextlib import closing

from src.languages import get_profile
from src.models import Translation

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "1"
POS = {
    "NOUN": ("noun",),
    "PROPN": ("name",),
    "VERB": ("verb",),
    "AUX": ("verb",),
    "ADJ": ("adj",),
    "ADV": ("adv",),
    "PRON": ("pron",),
    "DET": ("det", "article"),
    "ADP": ("prep", "postp"),
    "CCONJ": ("conj",),
    "SCONJ": ("conj",),
    "NUM": ("num",),
    "PART": ("particle",),
    "INTJ": ("intj",),
}
PAIRS = {("en", "ru"), ("es", "ru"), ("es", "en")}


def clean_word(word):
    # Remove Wiktionary's optional Russian stress mark, preserving Spanish accents.
    if any("\u0400" <= char <= "\u04ff" for char in word):
        word = word.replace("\u0301", "")
    return unicodedata.normalize("NFC", word).strip()


def translation_rows(entry):
    """Use explicit translation pairs in either direction, never definitions or a pivot language."""
    source, word, pos = entry.get("lang_code"), entry.get("word", ""), entry.get("pos")
    if source not in {"ru", "es", "en"} or not word or not pos:
        return
    word = clean_word(word)
    groups = [entry, *entry.get("senses", [])]
    for group in groups:
        if {"form-of", "obsolete", "archaic"} & set(group.get("tags", [])) or group.get("form_of"):
            continue
        for translation in group.get("translations", []):
            target = translation.get("lang_code") or translation.get("code")
            value = clean_word(translation.get("word", ""))
            if not value or {"obsolete", "archaic"} & set(translation.get("tags", [])):
                continue
            if (source, target) in PAIRS:
                yield (source, word.casefold(), pos, target, value, 0)
            if (target, source) in PAIRS:
                yield (target, value.casefold(), pos, source, word, 1)


def translate_entries(entries, dictionary_path, language):
    try:
        return _translate_entries(entries, dictionary_path, language)
    except (sqlite3.Error, OSError) as exc:
        logger.warning(
            "Kaikki unavailable: %s. Leaving translations blank. "
            "Reinstall: python -m src.translation.download --force", exc
        )
        return [Translation(entry["id"], error="kaikki dictionary unavailable") for entry in entries]


def _translate_entries(entries, dictionary_path, language):
    if not entries:
        return []
    if not dictionary_path.is_file():
        logger.warning(
            "Словарь Kaikki не установлен: выполните python -m src.translation.download. "
            "Переводы оставлены пустыми."
        )
        return [Translation(entry["id"], error="kaikki dictionary missing") for entry in entries]
    results = []
    # Read-only: the processing pipeline never downloads or changes the dictionary.
    with closing(sqlite3.connect(dictionary_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        for entry in entries:
            result = Translation(entry["id"])
            pos_values = POS.get(entry["pos"], ())
            word = clean_word(entry.get("form", entry["lemma"])).casefold()
            for target in get_profile(language).translation_targets:
                values = []
                for pos in pos_values:
                    rows = db.execute(
                        "SELECT value FROM translations WHERE language=? AND word=? AND pos=? AND target=? "
                        "ORDER BY priority, rowid LIMIT 20",
                        (language, word, pos, target),
                    )
                    for (value,) in rows:
                        if (
                            value.casefold() not in {v.casefold() for v in values}
                            and len(", ".join([*values, value])) <= 180
                        ):
                            values.append(value)
                        if len(values) >= 5:
                            break
                setattr(result, target, ", ".join(values[:5]))
            missing = [
                target for target in get_profile(language).translation_targets if not getattr(result, target)
            ]
            if missing:
                result.error = "kaikki: no translation for " + ", ".join(missing)
            results.append(result)
    logger.info("Kaikki: %d записей; с пропусками: %d.", len(results), sum(bool(r.error) for r in results))
    return results
