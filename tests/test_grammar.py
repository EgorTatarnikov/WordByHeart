import copy

import pytest

from src.aggregation.aggregator import aggregate
from src.config import Config
from src.grammar.adjectives import paradigm
from src.grammar.enrichment import enrich, load_lexicon
from src.grammar.nouns import enrich_noun, plural
from src.grammar.pos_mapping import format_morph
from src.grammar.verbs import enrich_verb
from src.models import GrammarInfo


def test_observed_vs_generated(observations):
    cfg = Config()
    lemmas, forms = aggregate(observations, cfg.aggregation, cfg.filters)
    before = copy.deepcopy((lemmas, forms))
    grammar, _ = enrich(lemmas, forms, cfg.grammar)
    small = next(r for r in lemmas if r["lemma"] == "pequeño")
    assert small["observed_forms"] == {"pequeña": 1}
    generated = next(g for g in grammar if g.id == small["id"])
    assert generated.grammar_forms == "pequeño / pequeña / pequeños / pequeñas"
    casa = next(r for r in lemmas if r["lemma"] == "casa")
    noun = next(g for g in grammar if g.id == casa["id"])
    assert noun.grammar_forms == "la casa / las casas"
    assert (lemmas, forms) == before


@pytest.mark.parametrize(
    "word,expected",
    [
        ("casa", "casas"),
        ("libro", "libros"),
        ("luz", "luces"),
        ("canción", "canciones"),
        ("lápiz", "lápices"),
        ("joven", "jóvenes"),
        ("crisis", "crisis"),
        ("rubí", ""),
    ],
)
def test_plural(word, expected):
    assert plural(word, load_lexicon()["nouns"]) == expected


@pytest.mark.parametrize(
    "word,morph,expected",
    [
        ("agua", "Gender=Fem", "el agua"),
        ("mano", "Gender=Fem", "la mano"),
        ("libro", "Gender=Masc", "el libro"),
        ("artista", "", ""),
        ("ave", "Gender=Fem", ""),
    ],
)
def test_article(word, morph, expected):
    info = GrammarInfo("test")
    enrich_noun({"lemma": word, "morph_variants": [morph]}, info, load_lexicon(), [])
    assert info.learning_form == expected
    if word == "agua":
        assert info.plural_form == "las aguas"
        assert info.grammatical_gender == "женский"
    if not expected:
        assert info.review


def test_gender_conflict():
    info = GrammarInfo("x")
    enrich_noun({"lemma": "casa", "morph_variants": ["Gender=Masc", "Gender=Fem"]}, info, load_lexicon(), [])
    assert not info.grammatical_gender
    assert info.review


def test_adjective_and_verbs():
    lexicon = load_lexicon()
    assert paradigm("interesante", lexicon) == ["interesante", "interesantes"]
    assert paradigm("feliz", lexicon) == ["feliz", "felices"]
    assert paradigm("azul", lexicon) == []  # Conservative unsupported class.
    for word, group, regularity in [
        ("tener", "-er", "irregular"),
        ("hablar", "-ar", "regular"),
        ("inventar", "-ar", "unknown"),
    ]:
        info = GrammarInfo("x")
        enrich_verb({"lemma": word}, info, lexicon)
        assert (info.conjugation_group, info.regularity) == (group, regularity)


def test_morph_format_preserves_unknown():
    result = format_morph("Mood=Ind|Number=Sing|Person=3|Tense=Imp|VerbForm=Fin|Other=Value")
    assert all(
        v in result for v in ["Indicativo", "единственное число", "3 лицо", "Imperfecto", "Other=Value"]
    )
