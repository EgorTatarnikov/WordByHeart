"""The single source of truth for translation coverage eligibility."""

from dataclasses import dataclass

from src.lemma_groups import group_lemmas

_EPSILON = 1e-12


@dataclass(frozen=True)
class TranslationSelection:
    requested_coverage: float
    actual_coverage: float
    eligible_lemma_ids: frozenset[str]
    eligible_form_ids: frozenset[str]


def select_lemmas_by_cumulative_coverage(
    lemmas: list[dict],
    forms: list[dict],
    cumulative_coverage_limit: float,
    specificity_threshold: float = 2.0,
    min_book_occurrences: int = 3,
) -> TranslationSelection:
    """Select whole lemma groups, counting each group's occurrences once."""
    groups = group_lemmas(lemmas, forms)
    selected = []
    target = cumulative_coverage_limit / 100
    for group in groups:
        selected.append(group)
        if cumulative_coverage_limit < 100 and group["cumulative_coverage"] >= target - _EPSILON:
            break
    selected_names = {g["lemma"] for g in selected}
    selected_names.update(
        g["lemma"]
        for g in groups
        if g["specificity"] >= specificity_threshold and g["count"] >= min_book_occurrences
    )
    lemma_ids = frozenset(row["id"] for row in lemmas if row["lemma"] in selected_names)
    eligible_keys = {(row["lemma"], row["pos"]) for row in lemmas if row["id"] in lemma_ids}
    form_ids = frozenset(row["id"] for row in forms if (row["lemma"], row["pos"]) in eligible_keys)
    actual = sum(g["count"] for g in groups if g["lemma"] in selected_names)
    total = sum(g["count"] for g in groups)
    return TranslationSelection(
        cumulative_coverage_limit, actual / total if total else 0.0, lemma_ids, form_ids
    )
