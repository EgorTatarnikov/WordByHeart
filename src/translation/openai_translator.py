import json
import logging
import math
import time
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tqdm import tqdm

from src.cache import SQLiteCache
from src.models import Translation
from src.storage import canonical

from .cache import cache_key
from .prompts import EN_SYSTEM_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class TranslationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    ru: str = Field(min_length=1)
    en: str = Field(min_length=1)


class TranslationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    entries: list[TranslationResult]


def parse_response(raw: str, expected: set[str], language="es") -> list[dict]:
    batch = TranslationBatch.model_validate_json(raw) if language == "es" else None
    entries = [r.model_dump() for r in batch.entries] if batch else json.loads(raw).get("entries", [])
    if language == "en" and (
        not isinstance(entries, list)
        or any(
            set(r) != {"id", "ru"}
            or not isinstance(r["id"], str)
            or not isinstance(r["ru"], str)
            or not r["ru"].strip()
            for r in entries
        )
    ):
        raise ValueError("Invalid English translation schema")
    ids = [r["id"] for r in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Дублирующиеся translation IDs")
    if not set(ids) <= expected:
        raise ValueError("Неизвестные translation IDs")
    if language == "es" and any(not r["ru"].strip() or not r["en"].strip() for r in entries):
        raise ValueError("Пустой перевод")
    return entries


class OpenAITranslator:
    def __init__(self, config, client=None, language="es"):
        if not config.model.strip():
            raise ValueError("Укажите machine_translation.model в config.yaml")
        if client is None:
            from openai import OpenAI

            client = OpenAI(timeout=config.timeout, max_retries=0)
        self.client, self.config, self.language = client, config, language

    def translate(self, entries):
        response = self.client.responses.create(
            model=self.config.model,
            store=False,
            input=[
                {"role": "system", "content": EN_SYSTEM_PROMPT if self.language == "en" else SYSTEM_PROMPT},
                {"role": "user", "content": canonical(entries)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "dictionary_translations",
                    "strict": True,
                    "schema": TranslationBatch.model_json_schema()
                    if self.language == "es"
                    else {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "entries": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {"id": {"type": "string"}, "ru": {"type": "string"}},
                                    "required": ["id", "ru"],
                                },
                            }
                        },
                        "required": ["entries"],
                    },
                }
            },
        )
        if response.status != "completed" or not response.output_text:
            raise ValueError("OpenAI: incomplete response or refusal")
        return parse_response(response.output_text, {e["id"] for e in entries}, self.language)


def translation_cache_counts(entries, config, cache_path, language="es") -> tuple[int, int]:
    """Return (cached, new) without mutating the cache or contacting a provider."""
    with SQLiteCache(cache_path) as cache:
        cached = sum(cache.get(cache_key(entry, config, language)) is not None for entry in entries)
    return cached, len(entries) - cached


def translate_entries(entries, config, cache_path, provider=None, language="es"):
    from openai import APIConnectionError, APIStatusError

    results, missing = {}, []
    with SQLiteCache(cache_path) as cache:
        for entry in entries:
            hit = cache.get(cache_key(entry, config, language))
            if hit is not None:
                validated = parse_response(json.dumps({"entries": [hit]}), {entry["id"]}, language)[0]
                if validated["id"] != entry["id"]:
                    raise ValueError("Translation cache ID mismatch")
                results[entry["id"]] = validated
            else:
                missing.append(entry)
        logger.info(
            "Перевод: из кэша %d; новых через API %d; пакетов %d.",
            len(results),
            len(missing),
            math.ceil(len(missing) / config.batch_size),
        )
        logger.debug("Перевод: символов во входящих запросах %d.", len(canonical(missing)))
        if missing and provider is None:
            if config.provider != "openai":
                raise ValueError(f"Неизвестный machine_translation provider: {config.provider}")
            provider = OpenAITranslator(config, language=language)
        api_requests = 0
        retries = Counter()

        def translate_batches(batch_entries, batch_size, show_progress):
            """Translate a pass and defer unsuccessful entries for a smaller pass."""
            nonlocal api_requests
            unresolved, errors = [], Counter()
            starts = range(0, len(batch_entries), batch_size)
            if show_progress:
                starts = tqdm(starts, desc="Translation")
            for start in starts:
                pending = batch_entries[start : start + batch_size]
                last_error = "missing IDs"
                for attempt in range(config.max_attempts):
                    try:
                        api_requests += 1
                        translated = provider.translate(pending)
                        # Validate also injected/third-party providers. Partial valid batches are committed.
                        translated = parse_response(
                            json.dumps({"entries": translated}), {e["id"] for e in pending}, language
                        )
                        by_id = {e["id"]: e for e in pending}
                        for item in translated:
                            cache.put(cache_key(by_id[item["id"]], config, language), item)
                            results[item["id"]] = item
                        pending = [e for e in pending if e["id"] not in results]
                        if not pending:
                            break
                        last_error = "missing IDs in partial batch"
                    except APIStatusError as exc:
                        if exc.status_code not in {408, 409, 429} and exc.status_code < 500:
                            raise
                        last_error = f"API status {exc.status_code}"
                    except (APIConnectionError, ValueError, ValidationError) as exc:
                        last_error = type(exc).__name__
                    if attempt + 1 < config.max_attempts:
                        retries[last_error] += 1
                        time.sleep(min(2**attempt, 30))
                if pending:
                    unresolved.extend(pending)
                    errors[last_error] += len(pending)
            return unresolved, errors

        batch_size = max(1, min(config.batch_size, len(missing)))
        unresolved, final_errors = translate_batches(missing, batch_size, show_progress=True)
        while unresolved and batch_size > 1:
            next_batch_size = max(1, batch_size // 2)
            logger.warning(
                "Перевод: %d записей не обработаны; повторяем пакетами по %d.",
                len(unresolved),
                next_batch_size,
            )
            unresolved, final_errors = translate_batches(unresolved, next_batch_size, show_progress=False)
            batch_size = next_batch_size
        if unresolved:
            details = ", ".join(f"{error}: {count}" for error, count in sorted(final_errors.items()))
            raise RuntimeError(
                f"Перевод не завершён: {len(unresolved)} IDs ({details}). Успешные ответы сохранены в cache."
            )
        if retries:
            details = ", ".join(f"{error}: {count}" for error, count in sorted(retries.items()))
            logger.warning("Перевод: повторено API-запросов %d (%s).", sum(retries.values()), details)
        logger.info("Переводы готовы: %d; API-запросов с повторами: %d.", len(missing), api_requests)
    return [Translation(**results[e["id"]]) for e in entries]
