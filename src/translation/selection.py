"""The single source of truth for translation coverage eligibility."""

from dataclasses import dataclass

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
    """Select the shortest frequency prefix that reaches the requested percentage.

    Aggregation stores cumulative coverage as a fraction in the [0, 1] range.  The
    explicit 100% path avoids a floating-point comparison excluding a final row.
    """
    ordered_lemmas = sorted(lemmas, key=lambda row: (-row["count"], row["lemma"], row["pos"]))
    target = cumulative_coverage_limit / 100
    if cumulative_coverage_limit >= 100:
        selected = ordered_lemmas
    else:
        selected = []
        for row in ordered_lemmas:
            selected.append(row)
            if row["cumulative_coverage"] >= target - _EPSILON:
                break

    coverage_ids = {row["id"] for row in selected}
    specificity_ids = {
        row["id"]
        for row in lemmas
        if row.get("specificity", 0.0) >= specificity_threshold and row["count"] >= min_book_occurrences
    }
    lemma_ids = frozenset(coverage_ids | specificity_ids)
    eligible_keys = {(row["lemma"], row["pos"]) for row in lemmas if row["id"] in lemma_ids}
    form_ids = frozenset(row["id"] for row in forms if (row["lemma"], row["pos"]) in eligible_keys)
    actual = selected[-1]["cumulative_coverage"] if selected else 0.0
    return TranslationSelection(cumulative_coverage_limit, actual, lemma_ids, form_ids)
