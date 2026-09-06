import json
import logging
import math
import time
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tqdm import tqdm

from src.cache import SQLiteCache
from src.models import Translation
from src.storage import canonical, read_rows, write_rows

from .cache import cache_key
from .prompts import EN_SYSTEM_PROMPT, SYSTEM_PROMPT
from .selection import TranslationSelection, select_lemmas_by_cumulative_coverage

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
            raise ValueError("Укажите translation.model в config.yaml")
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


def prepare_entries(lemmas, forms, config):
    entries = []
    for kind, rows in (("lemma", lemmas), ("form", forms)):
        for row in rows:
            entry = {
                "id": row["id"],
                "kind": kind,
                "lemma": row["lemma"],
                "pos": row["pos"],
                "morph_variants": row["morph_variants"],
                "contexts": row["contexts"][: config.max_contexts],
            }
            if kind == "form":
                entry["form"] = row["form"]
            else:
                entry["observed_forms"] = dict(
                    sorted(row["observed_forms"].items(), key=lambda x: (-x[1], x[0]))[:10]
                )
            entries.append(entry)
    return entries


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
                raise ValueError(f"Неизвестный translation provider: {config.provider}")
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


def log_selection(
    selection: TranslationSelection, lemmas: list[dict], forms: list[dict], config, cache_path, language="es"
):
    eligible_lemmas = [row for row in lemmas if row["id"] in selection.eligible_lemma_ids]
    eligible_forms = [row for row in forms if row["id"] in selection.eligible_form_ids]
    all_entries = prepare_entries(lemmas, forms, config)
    entries_by_id = {entry["id"]: entry for entry in all_entries}
    lemma_entries = [entries_by_id[row["id"]] for row in eligible_lemmas]
    form_entries = [entries_by_id[row["id"]] for row in eligible_forms]
    lemma_cached, lemma_new = translation_cache_counts(lemma_entries, config, cache_path, language)
    form_cached, form_new = translation_cache_counts(form_entries, config, cache_path, language)
    logger.info(
        "Перевод: coverage %.2f%%, фактически %.2f%%.",
        selection.requested_coverage,
        selection.actual_coverage * 100,
    )
    logger.info("Выбрано: %d лемм и %d словоформ.", len(eligible_lemmas), len(eligible_forms))
    logger.info(
        "Кэш переводов: %d; новых переводов через API: %d.",
        lemma_cached + form_cached,
        lemma_new + form_new,
    )
    return all_entries, lemma_entries + form_entries


def run(lemma_source, form_source, target, cache_path, config, provider=None, language="es"):
    if config.translate_examples:
        raise ValueError("translate_examples пока не реализован; установите false")
    lemmas, forms = read_rows(lemma_source), read_rows(form_source)
    selection = select_lemmas_by_cumulative_coverage(
        lemmas,
        forms,
        config.cumulative_coverage_limit,
        config.specificity_threshold,
        config.min_book_occurrences,
    )
    all_entries = prepare_entries(lemmas, forms, config)
    if not config.enabled:
        write_rows(
            target,
            [
                Translation(
                    entry["id"],
                    error="disabled",
                    translation_eligible=entry["id"] in selection.eligible_lemma_ids
                    or entry["id"] in selection.eligible_form_ids,
                )
                for entry in all_entries
            ],
        )
        return
    entries, eligible_entries = log_selection(selection, lemmas, forms, config, cache_path, language)
    translated = {
        item.id: item for item in translate_entries(eligible_entries, config, cache_path, provider, language)
    }
    result = []
    for entry in entries:
        eligible = entry["id"] in selection.eligible_lemma_ids or entry["id"] in selection.eligible_form_ids
        result.append(
            translated.get(
                entry["id"],
                Translation(
                    entry["id"],
                    error="outside cumulative coverage limit",
                    translation_eligible=eligible,
                ),
            )
        )
    write_rows(target, result)
