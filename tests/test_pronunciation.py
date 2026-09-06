import os

import pytest

from src.config import Pronunciation
from src.pronunciation.service import PhonemizerService, run
from src.storage import read_rows, write_rows


def test_unique_texts_cache_and_disabled(tmp_path, monkeypatch):
    calls = []

    class Service:
        def __init__(self, language):
            self.version = "test"

        def phonemize(self, texts):
            calls.append(texts)
            return ["kˈasa" for _ in texts]

    monkeypatch.setattr("src.pronunciation.service.PhonemizerService", Service)
    lemmas, forms, target, cache = [
        tmp_path / name for name in ["lemmas.parquet", "forms.parquet", "ipa.parquet", "cache.sqlite"]
    ]
    write_rows(lemmas, [{"lemma": "casa"}, {"lemma": "casa"}])
    write_rows(forms, [{"form": "casa"}, {"form": "123"}])
    config = Pronunciation()
    run(lemmas, forms, target, cache, config)
    assert calls == [["casa"]]
    assert len(read_rows(target)) == 2
    assert read_rows(target)[0]["error"].startswith("unsupported")
    run(lemmas, forms, target, cache, config)
    assert calls == [["casa"]]
    config.language = "es-419"
    run(lemmas, forms, target, cache, config)
    assert calls == [["casa"], ["casa"]]
    config.enabled = False
    run(lemmas, forms, target, cache, config)
    assert all(r["error"] == "disabled" for r in read_rows(target))


@pytest.mark.integration
def test_actual_espeak_variants():
    if not os.environ.get("TEST_ESPEAK"):
        pytest.skip("Set TEST_ESPEAK=1 with eSpeak NG configured")
    spain = PhonemizerService("es").phonemize(["casa", "cielo"])
    latin = PhonemizerService("es-419").phonemize(["casa", "cielo"])
    assert all(spain) and all(latin)
    assert spain[0] == latin[0]
    assert "θ" in spain[1]
    assert "θ" not in latin[1] and "s" in latin[1]
