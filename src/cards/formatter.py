import math
import re
import unicodedata
from collections.abc import Mapping

_ARTICLES = frozenset({"el", "la", "los", "las", "un", "una", "unos", "unas"})
_FRONT_SEPARATORS = re.compile(r"\s*(?:/|;|\||,)\s*")


def has_value(value) -> bool:
    return not (
        value is None
        or (isinstance(value, float) and math.isnan(value))
        or (isinstance(value, str) and not value.strip())
    )


def get_card_front_text(entry) -> str:
    for value in (entry.grammatical_forms, entry.learning_form, entry.lemma):
        if has_value(value):
            return str(value).strip()
    return ""


def normalize_card_form(text: str) -> str:
    """Normalize text only for matching a displayed form to an observed form."""
    return unicodedata.normalize("NFC", str(text)).strip().casefold()


def extract_forms_from_front(front_text: str, strip_articles=True) -> set[str]:
    """Return lexical forms visibly represented on a card front.

    Spanish articles are presentation aids on the front: ``la casa`` visibly
    represents the observed form ``casa``.
    """
    result = set()
    for part in _FRONT_SEPARATORS.split(front_text):
        normalized = normalize_card_form(part)
        if not normalized:
            continue
        words = normalized.split(maxsplit=1)
        if strip_articles and words[0] in _ARTICLES and len(words) == 2:
            normalized = words[1]
        if normalized:
            result.add(normalized)
    return result


def select_observed_forms(forms: Mapping[str, int] | None, max_forms: int = 10) -> list[str]:
    if not forms:
        return []
    return [form for form, _ in sorted(forms.items(), key=lambda item: (-item[1], item[0]))[:max_forms]]


def filter_observed_forms_for_back(
    observed_forms: Mapping[str, int] | None, front_text: str, max_forms: int = 10, strip_articles=True
) -> list[str]:
    front_forms = extract_forms_from_front(front_text, strip_articles)
    selected = []
    seen = set()
    for form, _ in sorted((observed_forms or {}).items(), key=lambda item: (-item[1], item[0])):
        normalized = normalize_card_form(form)
        if not normalized or normalized in front_forms or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(form)
        if len(selected) == max_forms:
            break
    return selected


def format_observed_forms(forms: list[str]) -> str:
    return ", ".join(forms)


def english_back_forms(entry, max_forms: int = 10) -> list[str]:
    """Return generated and observed English forms for a card back."""
    front = normalize_card_form(entry.learning_form or entry.lemma)
    candidates = _FRONT_SEPARATORS.split(entry.grammatical_forms or "")
    candidates.extend(select_observed_forms(entry.observed_forms, max_forms))
    result, seen = [], {front}
    for form in candidates:
        normalized = normalize_card_form(form)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(form.strip())
    return result


def get_forms_font_size(text: str, normal_size: int, threshold: int, reduced_size: int) -> int:
    return reduced_size if len(text) > threshold else normal_size


def get_translation_font_size(text: str, normal_size: int, threshold: int, reduced_size: int) -> int:
    return reduced_size if len(text) > threshold else normal_size
