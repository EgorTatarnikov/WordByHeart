from dataclasses import asdict

import pytest
from openpyxl import load_workbook

from src.cards.formatter import card_content
from src.cards.learning_list import render_learning_list
from src.cards.selector import select_cards
from src.config import Cards, Grammar
from src.grammar.enrichment import enrich


@pytest.mark.parametrize(
    "lemma,expected_front,expected_forms",
    [
        ("niña", "el niño", "la niña, los niños, las niñas"),
        ("estudiante", "el estudiante", "la estudiante, los estudiantes, las estudiantes"),
    ],
)
def test_gender_pair_from_feminine_or_shared_lemma(tmp_path, lemma, expected_front, expected_forms):
    rows = [{
        "id": "noun", "lemma": lemma, "pos": "NOUN", "count": 5,
        "morph_variants": ["Gender=Fem|Number=Sing"], "observed_forms": {lemma: 5},
    }]
    grammar, _ = enrich(rows, [], Grammar(), "es")
    data = {
        "lemmas": rows, "forms": [], "lemma_grammar": [asdict(grammar[0])],
        "ipa": [{"text": "niño" if lemma == "niña" else lemma, "ipa": "nˈiɲo"}],
        "translations": [{"id": "noun", "ru": "ребёнок", "en": "child"}],
    }
    cards, _ = select_cards(data, 100, min_book_occurrences=1, language="es")
    assert len(cards) == 1
    front, ipa, _, forms = card_content(cards[0], language="es")
    assert (front, forms) == (expected_front, expected_forms)
    assert ipa == "/nˈiɲo/"

    target = tmp_path / "spanish_list.xlsx"
    render_learning_list(cards, target, Cards(), "es")
    book = load_workbook(target, read_only=True)
    try:
        sheet = book.active
        assert [cell.value for cell in sheet[1]][:3] == [
            "Слово", "Транскрипция", "Транскрипция Кириллица"
        ]
        assert sheet["A2"].value == expected_front
        assert sheet["E2"].value == expected_forms
    finally:
        book.close()


def test_masculine_and_feminine_lemmas_share_one_card():
    lemmas = [
        {"id": "male", "lemma": "niño", "pos": "NOUN", "count": 6, "observed_forms": {"niño": 6}},
        {"id": "female", "lemma": "niña", "pos": "NOUN", "count": 4, "observed_forms": {"niña": 4}},
    ]
    data = {
        "lemmas": lemmas, "forms": [],
        "lemma_grammar": [{"id": row["id"]} for row in lemmas],
        "ipa": [{"text": "niño", "ipa": "nˈiɲo"}],
        "translations": [{"id": row["id"], "ru": "ребёнок", "en": "child"} for row in lemmas],
    }
    cards, _ = select_cards(data, 100, min_book_occurrences=1, language="es")
    assert len(cards) == 1
    assert cards[0].observed_forms == {"niño": 6, "niña": 4}
    assert card_content(cards[0], language="es")[3] == "la niña, los niños, las niñas"
