"""Small, explicit registry for supported source languages."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    wordfreq_language: str
    default_nlp_model: str
    default_pronunciation_language: str
    translation_targets: tuple[str, ...]
    export_filename: str
    cards_show_english_translation: bool
    strip_articles_on_card_front: bool


_PROFILES = {
    "es": LanguageProfile(
        "es",
        "es",
        "es_dep_news_trf",
        "es",
        ("ru", "en"),
        "spanish_frequency_dictionary.xlsx",
        True,
        True,
    ),
    "en": LanguageProfile(
        "en",
        "en",
        "en_core_web_trf",
        "en-us",
        ("ru",),
        "english_frequency_dictionary.xlsx",
        False,
        False,
    ),
}


def get_profile(language: str) -> LanguageProfile:
    try:
        return _PROFILES[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported language: {language!r}; supported: {', '.join(_PROFILES)}") from exc
