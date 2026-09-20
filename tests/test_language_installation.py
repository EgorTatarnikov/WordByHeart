import json

import yaml

from src.languages.installation import language_is_installed
from src.translation.download import editions_for_languages


def test_english_and_spanish_kaikki_editions_are_separate():
    assert editions_for_languages(("en",)) == {"ru"}
    assert editions_for_languages(("es",)) == {"ru", "es"}


def test_spanish_requires_model_and_spanish_dictionary_data(tmp_path, monkeypatch):
    config = tmp_path / "config"
    cache = tmp_path / "data" / "cache" / "kaikki"
    config.mkdir()
    cache.mkdir(parents=True)
    (config / "demo_es.yaml").write_text(
        yaml.safe_dump({"language": "es", "paths": {"cache": "../data/cache"}, "nlp": {"model": "spanish_test_model"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.languages.installation.importlib.util.find_spec", lambda _name: object())

    (cache / "SOURCES.json").write_text(json.dumps({"editions": ["ru"]}), encoding="utf-8")
    assert not language_is_installed(tmp_path, "es")

    (cache / "SOURCES.json").write_text(json.dumps({"editions": ["ru", "es"]}), encoding="utf-8")
    assert language_is_installed(tmp_path, "es")
