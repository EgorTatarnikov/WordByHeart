"""Build a per-book runtime config without changing the demo YAML files."""

import hashlib
from pathlib import Path

import yaml

from src.config import Config, load_config

LANGUAGES = {"English": "en", "Español": "es"}


def build_config(root, source, language, options):
    source = Path(source).expanduser().resolve()
    if source.suffix.lower() != ".txt" or not source.is_file():
        raise ValueError("Выберите существующий TXT-файл.")
    if source.stat().st_size == 0:
        raise ValueError("Выбранный TXT-файл пуст.")
    if language not in LANGUAGES.values():
        raise ValueError("Выберите English или Español.")
    demo = root / "config" / f"demo_{language}.yaml"
    cfg = load_config(demo)
    cfg.cards.enabled = bool(options["cards"])
    cfg.machine_translation.enabled = bool(options["machine"])
    cfg.known_dictionary.enabled = bool(options["known"])
    cfg.pronunciation.enabled = bool(options["ipa"])
    cfg.translation.cumulative_coverage_limit = float(options["coverage"])
    cfg.translation.specificity_threshold = float(options["specificity"])
    cfg.translation.min_book_occurrences = int(options["occurrences"])
    # Revalidate assignments before any files are written.
    cfg = Config.model_validate(cfg.model_dump())
    for name in ("cache",):
        setattr(cfg.paths, name, str((demo.parent / getattr(cfg.paths, name)).resolve()))
    cfg.cards.template = str((demo.parent / cfg.cards.template).resolve())
    known = cfg.known_dictionary.path or f"../my_dictionary_{language}.xlsx"
    cfg.known_dictionary.path = str((demo.parent / known).resolve())
    if cfg.grammar.lexicon:
        cfg.grammar.lexicon = str((demo.parent / cfg.grammar.lexicon).resolve())
    if cfg.cards.enabled and not Path(cfg.cards.template).is_file():
        raise ValueError("Не найден шаблон карточек. Восстановите ваш table.docx в корне приложения.")
    if cfg.known_dictionary.enabled and not Path(cfg.known_dictionary.path).is_file():
        raise ValueError("Не найден список известных слов. Отключите исключение известных слов.")
    book = hashlib.sha256(str(source).encode()).hexdigest()[:12] + "-" + language
    cfg.paths.work = str(root / "data" / "work" / "gui" / book)
    cfg.paths.output = str(root / "data" / "output" / "gui" / book)
    config_path = Path(cfg.paths.work) / "run.yaml"
    return source, config_path, cfg


def save_config(path, cfg):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        yaml.safe_dump(cfg.model_dump(), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    temporary.replace(path)
