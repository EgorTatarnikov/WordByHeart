from dataclasses import asdict

import pytest

from src.models import Occurrence


@pytest.fixture
def observations():
    specs = [
        ("Juan", "Juan", "PROPN", "Gender=Masc|Number=Sing", "Juan vino a casa."),
        (
            "vino",
            "venir",
            "VERB",
            "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin",
            "Juan vino a casa.",
        ),
        ("a", "a", "ADP", "", "Juan vino a casa."),
        ("casa", "casa", "NOUN", "Gender=Fem|Number=Sing", "Juan vino a casa."),
        ("El", "el", "DET", "Gender=Masc|Number=Sing", "El vino era bueno."),
        ("vino", "vino", "NOUN", "Gender=Masc|Number=Sing", "El vino era bueno."),
        ("La", "el", "DET", "Gender=Fem|Number=Sing", "La casa es pequeña."),
        ("casa", "casa", "NOUN", "Gender=Fem|Number=Sing", "La casa es pequeña."),
        ("pequeña", "pequeño", "ADJ", "Gender=Fem|Number=Sing", "La casa es pequeña."),
        ("casas", "casa", "NOUN", "Gender=Fem|Number=Plur", "Las casas son bonitas."),
        ("Casa", "casa", "NOUN", "Gender=Fem|Number=Sing", "Casa es una palabra."),
        ("CASA", "casa", "NOUN", "Gender=Fem|Number=Sing", "CASA es una palabra."),
        (".", ".", "PUNCT", "", "La casa es pequeña."),
    ]
    return [
        asdict(
            Occurrence(
                text,
                text.casefold(),
                lemma,
                pos,
                morph,
                text.isalpha(),
                pos == "PUNCT",
                False,
                context,
                i // 4,
                i // 4,
                i // 4,
                i,
            )
        )
        for i, (text, lemma, pos, morph, context) in enumerate(specs)
    ]
