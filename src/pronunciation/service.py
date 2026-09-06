import logging

from tqdm import tqdm

from src.cache import SQLiteCache
from src.models import Pronunciation
from src.storage import read_rows, write_rows

from .cache import cache_key

logger = logging.getLogger(__name__)


class PhonemizerService:
    def __init__(self, language):
        from phonemizer.backend import EspeakBackend

        if language not in EspeakBackend.supported_languages():
            raise ValueError(f"eSpeak NG не поддерживает вариант {language}; проверьте установленную версию")
        self.backend = EspeakBackend(
            language, with_stress=True, preserve_punctuation=False, language_switch="remove-flags"
        )
        self.version = str(EspeakBackend.version())

    def phonemize(self, texts):
        return [p.strip() for p in self.backend.phonemize(texts, strip=True)]


def run(lemma_source, form_source, target, cache_path, config):
    texts = sorted(
        {r["lemma"] for r in read_rows(lemma_source)} | {r["form"] for r in read_rows(form_source)}
    )
    if not config.enabled:
        write_rows(target, [Pronunciation(t, config.language, error="disabled") for t in texts])
        return
    service = PhonemizerService(config.language)
    result, pending = {}, []
    with SQLiteCache(cache_path) as cache:
        for text in texts:
            cached = cache.get(cache_key(text, config.language, service.version))
            if cached:
                result[text] = Pronunciation(text, config.language, cached["ipa"])
            elif not text.isalpha():
                result[text] = Pronunciation(
                    text, config.language, error="unsupported input: non-alphabetic token"
                )
            else:
                pending.append(text)
        logger.info(
            "IPA cache hits: %d; pending: %d", sum(bool(p.ipa) for p in result.values()), len(pending)
        )
        for start in tqdm(range(0, len(pending), config.batch_size), desc="IPA"):
            batch = pending[start : start + config.batch_size]
            values = service.phonemize(batch)
            if len(values) != len(batch):
                raise RuntimeError("Phonemizer вернул неверное количество записей")
            for text, ipa in zip(batch, values):
                result[text] = Pronunciation(text, config.language, ipa, "" if ipa else "empty IPA")
                if ipa:
                    cache.put(cache_key(text, config.language, service.version), {"ipa": ipa})
    write_rows(target, [result[t] for t in texts])
    logger.info("Количество IPA: %d", sum(bool(p.ipa) for p in result.values()))
