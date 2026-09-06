import copy
import unicodedata

import pytest

from src.aggregation.aggregator import aggregate
from src.config import Config
from src.preprocessing.chunker import chunks
from src.preprocessing.normalizer import normalize
from src.storage import read_rows, write_rows


def test_unicode_bom_case_punctuation():
    text = "\ufeff  ¿Pequen\u0303a?\r\n\r\n\tÁRBOL   azul.\r"
    value = normalize(text, Config().preprocess)
    assert value == "¿Pequeña?\n\nÁRBOL azul.\n"
    assert unicodedata.is_normalized("NFC", value)


def test_optional_cleaning():
    config = Config().preprocess.model_copy(
        update={"strip_gutenberg": True, "remove_page_numbers": True, "remove_lines": ["HEADER"]}
    )
    text = "Metadata\n*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\nHEADER\n12\nLa casa.\n*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\nLicense"
    assert normalize(text, config) == "La casa.\n"


@pytest.mark.parametrize("ending", ["", "\n", "\n\n"])
def test_chunks_keep_final_paragraph(ending):
    text = "Juan vino a casa.\n\nEl vino era bueno." + ending
    result = list(chunks(text, 100))
    assert [c.text for c in result] == ["Juan vino a casa.", "El vino era bueno."]
    assert [c.paragraph_id for c in result] == [0, 1]
    assert all(text[c.start_char : c.start_char + len(c.text)] == c.text for c in result)


def test_chunk_size_sentence_boundary_and_oversized_word():
    text = "Hola mundo. " * 100
    result = list(chunks(text, 100))
    assert "".join(c.text for c in result).strip() == text.strip()
    assert all(len(c.text) <= 100 for c in result)
    assert all(not c.split_sentence for c in result)
    text = "x" * 200 + " y " + "z" * 200
    result = list(chunks(text, 100))
    assert "".join(c.text for c in result) == text


def test_homonyms_case_counts_pos_contexts(observations):
    config = Config()
    lemmas, forms = aggregate(iter(observations), config.aggregation, config.filters)
    vino = {(r["form"], r["lemma"], r["pos"]) for r in forms if r["form"] == "vino"}
    assert vino == {("vino", "venir", "VERB"), ("vino", "vino", "NOUN")}
    casa = next(r for r in lemmas if r["lemma"] == "casa")
    assert casa["count"] == 5
    assert casa["observed_forms"] == {"casa": 4, "casas": 1}
    assert casa["chunk_count"] == 3
    assert len(casa["contexts"]) == 3
    assert sum(r["count"] for r in forms) == sum(r["count"] for r in lemmas) == 12
    assert lemmas[-1]["cumulative_coverage"] == 1
    assert sum(r["share"] for r in lemmas) == pytest.approx(1)
    form = next(r for r in forms if r["form"] == "casa")
    assert form["original_forms"] == ["CASA", "Casa", "casa"]
    assert any(r["pos"] == "DET" for r in lemmas)
    assert any(r["pos"] == "PROPN" for r in lemmas)


def test_same_lemma_different_pos_and_morph(observations):
    rows = copy.deepcopy(observations[:1]) * 3
    rows = [dict(r) for r in rows]
    rows[0].update(lemma="bajo", normalized_form="bajo", pos="ADJ", morph="Gender=Masc")
    rows[1].update(lemma="bajo", normalized_form="bajo", pos="ADP", morph="")
    rows[2].update(lemma="bajo", normalized_form="bajo", pos="ADJ", morph="Number=Sing")
    lemmas, forms = aggregate(rows, Config().aggregation, Config().filters)
    assert len(lemmas) == len(forms) == 2
    assert forms[0]["morph_variants"] == ["Gender=Masc", "Number=Sing"]


def test_filters_do_not_alter_occurrences(observations):
    before = copy.deepcopy(observations)
    config = Config()
    config.filters.include_function_words = False
    config.filters.include_proper_nouns = False
    lemmas, _ = aggregate(observations, config.aggregation, config.filters)
    assert not {"ADP", "DET", "PROPN"} & {r["pos"] for r in lemmas}
    assert observations == before


def test_parquet_roundtrip_and_empty(tmp_path, observations):
    path = tmp_path / "rows.parquet"
    rows, _ = aggregate(observations, Config().aggregation, Config().filters)
    write_rows(path, rows)
    assert read_rows(path) == rows
    write_rows(path, [], columns=["id", "message"])
    assert read_rows(path) == []
