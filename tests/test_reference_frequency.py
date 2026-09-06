import pytest

from src.reference_frequency.calculator import calculate_specificity, enrich


def test_specificity_uses_tiny_floor_only_for_zero_reference_frequency():
    assert calculate_specificity(0.0001, 0.00002) == pytest.approx(5)
    assert calculate_specificity(0.00001, 0.0) == pytest.approx(10_000_000)


def test_enriches_forms_and_sums_unique_observed_forms_for_lemma():
    lemmas = [
        {"id": "lemma:casa", "lemma": "casa", "pos": "NOUN", "count": 10, "share": 1.0},
    ]
    forms = [
        {"id": "form:casa", "form": "casa", "lemma": "casa", "pos": "NOUN", "count": 7},
        {"id": "form:casas", "form": "casas", "lemma": "casa", "pos": "NOUN", "count": 3},
    ]

    enriched_lemmas, enriched_forms = enrich(
        lemmas, forms, lookup=lambda form, language: {"casa": 0.01, "casas": 0.002}[form]
    )

    assert [row["reference_frequency"] for row in enriched_forms] == [0.01, 0.002]
    assert enriched_lemmas[0]["book_relative_frequency"] == 1.0
    assert enriched_lemmas[0]["reference_frequency"] == pytest.approx(0.012)
    assert enriched_lemmas[0]["specificity"] == pytest.approx(1 / 0.012)
