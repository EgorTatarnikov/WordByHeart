import pytest
import yaml

from src.config import Preprocess
from src.pipeline import Pipeline
from src.preprocessing.english_contractions import CONTRACTIONS_MAP, expand_contractions
from src.preprocessing.loader import run


@pytest.mark.parametrize("apostrophe", ["'", "’", "‘", "ʼ"])
def test_map_expansions(apostrophe):
    for word, expected in CONTRACTIONS_MAP.items():
        assert expand_contractions(word.replace("'", apostrophe)).lower() == expected


def test_ambiguous_forms_and_case_and_punctuation():
    text = "Wasn’t! YOU’LL, father's; he's. She’d, ain't. I'm here.\nYou’ve come."
    expected = "Was not! YOU, father; he. She’d, ain't. I am here.\nYou have come."
    assert expand_contractions(text) == expected
    assert expand_contractions(expected) == expected


@pytest.mark.parametrize("language", ["en", "es"])
def test_loader_language_and_encoding(tmp_path, language):
    source, target = tmp_path / "book.txt", tmp_path / "normalized.txt"
    source.write_bytes("Wasn’t ready. You’ll see father's book.".encode("cp1252"))
    run(source, target, Preprocess(), language)
    expected = (
        "Was not ready. You see father book."
        if language == "en" else "Wasn’t ready. You’ll see father's book."
    )
    assert target.read_text(encoding="utf-8") == expected + "\n"


def test_pipeline_preprocess_and_language_cache_invalidation(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"language": "en", "pronunciation": {"enabled": False}}))
    source = tmp_path / "book.txt"
    source.write_text("He wasn't sure. You'll see.", encoding="utf-8")
    pipeline = Pipeline(config, source)
    pipeline.run("preprocess")
    assert pipeline.outputs["preprocess"][0].read_text(encoding="utf-8") == "He was not sure. You see.\n"
    assert pipeline.status()["preprocess"][0] == "OK"
    config.write_text(yaml.safe_dump({"language": "es", "pronunciation": {"enabled": False}}))
    pipeline = Pipeline(config, source)
    assert pipeline.status()["preprocess"][0] == "OUTDATED"
    pipeline.run("preprocess")
    assert pipeline.outputs["preprocess"][0].read_text(encoding="utf-8") == "He wasn't sure. You'll see.\n"


def test_map_changes_invalidate_preprocess_cache(tmp_path, monkeypatch):
    import src.pipeline as module

    config = tmp_path / "config.yaml"
    config.write_text("language: en\npronunciation:\n  enabled: false\n")
    source = tmp_path / "book.txt"
    source.write_text("Wasn't ready.", encoding="utf-8")
    pipeline = Pipeline(config, source)
    pipeline.run("preprocess")
    original = module.file_hash
    monkeypatch.setattr(module, "file_hash", lambda p: "changed" if p.name == "english_contractions.py" else original(p))
    assert pipeline.status()["preprocess"][0] == "OUTDATED"
