"""Install Kaikki data separately from application code; no data is bundled."""

import argparse
import gzip
import hashlib
import json
import logging
import sqlite3
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from filelock import FileLock
from tqdm import tqdm

from src.config import load_config

from .kaikki import SCHEMA_VERSION, translation_rows
from .health import dictionary_is_healthy

SOURCES = {
    "ru": "https://kaikki.org/dictionary/downloads/ru/ru-extract.jsonl.gz",
    "es": "https://kaikki.org/dictionary/downloads/es/es-extract.jsonl.gz",
}
logger = logging.getLogger(__name__)


def download_file(url, target):
    """Retry transient network failures without replacing a previously valid archive."""
    for attempt in range(3):
        try:
            return _download_once(url, target)
        except httpx.TransportError:
            if attempt == 2:
                raise
            logger.warning("Kaikki: connection interrupted; retry %d/3", attempt + 2)
            time.sleep(2 * (attempt + 1))


def _download_once(url, target):
    """Atomic download with bounded network waits and visible byte progress."""
    part = target.with_suffix(target.suffix + ".part")
    try:
        with httpx.stream(
            "GET", url, follow_redirects=True, timeout=httpx.Timeout(90, connect=30)
        ) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0)) or None
            with (
                part.open("wb") as output,
                tqdm(total=total, unit="B", unit_scale=True, desc=target.name) as progress,
            ):
                for chunk in response.iter_bytes(1024 * 1024):
                    output.write(chunk)
                    progress.update(len(chunk))
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)


def build_index(sources, target):
    """Stream JSONL into a compact index and replace the old index only on success."""
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    count = 0
    try:
        with sqlite3.connect(temporary) as db:
            db.execute(
                "CREATE TABLE translations (language TEXT, word TEXT, pos TEXT, target TEXT, "
                "value TEXT, priority INTEGER, UNIQUE(language, word, pos, target, value))"
            )
            for source in sources:
                logger.info("Индексирование %s", source.name)
                opener = gzip.open if source.suffix == ".gz" else open
                with opener(source, "rt", encoding="utf-8") as stream:
                    for line in tqdm(stream, desc=source.name, unit=" entries"):
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        for value in translation_rows(row):
                            db.execute(
                                "INSERT INTO translations VALUES (?, ?, ?, ?, ?, ?) "
                                "ON CONFLICT(language,word,pos,target,value) DO UPDATE "
                                "SET priority=MIN(priority,excluded.priority)",
                                value,
                            )
                        count += 1
                        if count % 10000 == 0:
                            db.commit()
            db.execute("CREATE INDEX lookup ON translations(language,word,pos,target,priority)")
            db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO metadata VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
            total = db.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
            if not total:
                raise ValueError("В данных Kaikki не найдено переводов для поддерживаемых языков")
        # Explicit close is needed before rename on Windows (the context manager only commits).
        db.close()
        temporary.replace(target)
        return total
    finally:
        if "db" in locals():
            db.close()
        temporary.unlink(missing_ok=True)


def editions_for_languages(languages):
    editions = {"ru"}
    if "es" in languages:
        editions.add("es")
    return editions


def install(cache_dir, force=False, languages=("en",)):
    directory = Path(cache_dir) / "kaikki"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "dictionary.sqlite"
    with FileLock(str(directory / ".install.lock"), timeout=0):
        required_editions = editions_for_languages(languages)
        metadata_path = directory / "SOURCES.json"
        installed_editions = set()
        if metadata_path.is_file():
            try:
                installed_editions = set(json.loads(metadata_path.read_text(encoding="utf-8")).get("editions", []))
            except (OSError, ValueError):
                pass
        if required_editions <= installed_editions and not force and dictionary_is_healthy(target, full=True):
            logger.info("Kaikki уже установлен для %s", ", ".join(sorted(languages)))
            return target
        editions = installed_editions | required_editions
        sources = []
        provenance = []
        for edition in sorted(editions):
            url = SOURCES[edition]
            source = directory / f"{edition}-extract.jsonl.gz"
            if force or not source.is_file():
                download_file(url, source)
            sources.append(source)
            with source.open("rb") as stream:
                sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
            provenance.append({"url": url, "sha256": sha256})
        count = build_index(sources, target)
        (directory / "SOURCES.json").write_text(
            json.dumps(
                {
                    "installed_at": datetime.now(UTC).isoformat(),
                    "sources": provenance,
                    "editions": sorted(editions),
                    "source": "Kaikki.org / Wiktionary",
                    "schema_version": SCHEMA_VERSION,
                    "documentation": "https://kaikki.org/dictionary/rawdata.html",
                    "license": "https://en.wiktionary.org/wiki/Wiktionary:Copyrights",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("Kaikki: установлено %d переводов в %s", count, target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Скачать и проиндексировать словари Kaikki перед запуском")
    parser.add_argument(
        "--config", type=Path, nargs="+", default=[Path("config/demo_en.yaml"), Path("config/demo_es.yaml")]
    )
    parser.add_argument("--force", action="store_true", help="Скачать свежие данные и пересоздать индекс")
    parser.add_argument("--language", choices=("en", "es"), default="en")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        directories = {
            (path.resolve().parent / load_config(path).paths.cache).resolve() for path in args.config
        }
        for directory in sorted(directories):
            install(directory, args.force, (args.language,))
    except (OSError, ValueError, httpx.HTTPError, sqlite3.Error) as exc:
        logger.error("Не удалось установить Kaikki: %s. Повторите команду установки.", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
