from dataclasses import asdict

from src.aggregation.aggregator import aggregate
from src.config import Config
from src.grammar.enrichment import enrich
from src.models import Pronunciation, Translation
from src.validation.validator import Validator


def test_ambiguity_is_informational_and_missing_enrichment_flagged(observations):
    config = Config()
    lemmas, forms = aggregate(observations, config.aggregation, config.filters)
    lg, fg = enrich(lemmas, forms, config.grammar)
    grammar = [asdict(g) for g in lg + fg]
    pronunciations = [
        asdict(Pronunciation(text, "es", "ipa"))
        for text in {r["lemma"] for r in lemmas} | {r["form"] for r in forms}
    ]
    translations = [asdict(Translation(r["id"], "перевод", "translation")) for r in lemmas + forms]
    issues = Validator().validate(lemmas, forms, grammar, pronunciations, translations, config)
    ambiguity = [r for r in issues if r.category == "ambiguity"]
    assert len(ambiguity) == 2
    assert all(r.severity == "info" for r in ambiguity)
    translations[0]["ru"] = "**explanation**"
    translations.pop()
    issues = Validator().validate(lemmas, forms, grammar, [], translations, config)
    assert any(r.category == "ipa" for r in issues)
    assert any(r.message == "Отсутствующий ID" for r in issues)
    assert any("Markdown" in r.message for r in issues)
