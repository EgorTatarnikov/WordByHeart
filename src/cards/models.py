from dataclasses import dataclass


@dataclass(frozen=True)
class CardEntry:
    lemma: str
    pos: str
    rank: int
    grammatical_forms: str
    learning_form: str
    ipa: str
    translation_ru: str
    translation_en: str
    observed_forms: dict[str, int]
