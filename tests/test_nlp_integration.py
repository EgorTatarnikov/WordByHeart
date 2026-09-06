import importlib.util
import os

import pytest

from src.aggregation.aggregator import aggregate
from src.config import Config
from src.nlp.processor import run
from src.storage import read_rows


@pytest.mark.integration
@pytest.mark.parametrize("model", ["es_core_news_sm", "es_dep_news_trf"])
def test_actual_spacy_homonyms(tmp_path, model):
    selected = os.environ.get("TEST_SPACY_MODEL")
    if selected and selected != model:
        pytest.skip("Another model selected by TEST_SPACY_MODEL")
    if not importlib.util.find_spec(model):
        pytest.skip(f"Install {model} to run actual NLP integration")
    config = Config()
    config.nlp.model = model
    source, target = tmp_path / "text.txt", tmp_path / "occurrences.parquet"
    text = "Juan vino a casa.\nEl vino era bueno.\n\nLa casa es pequeña.\nLas casas son bonitas.\n"
    source.write_text(text, encoding="utf-8")
    run(source, target, config.nlp)
    occurrences = read_rows(target)
    assert all(r["context"] in text for r in occurrences)
    assert len({r["token_index"] for r in occurrences}) == len(occurrences)
    lemmas, forms = aggregate(occurrences, config.aggregation, config.filters)
    assert {(r["lemma"], r["pos"]) for r in forms if r["form"] == "vino"} == {
        ("venir", "VERB"),
        ("vino", "NOUN"),
    }
    assert all(
        "pequeños" not in r["observed_forms"] and "pequeñas" not in r["observed_forms"] for r in lemmas
    )
