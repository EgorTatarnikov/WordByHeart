import logging
from collections import defaultdict

from src.reference_frequency.calculator import calculate_specificity, get_reference_frequency
from src.storage import read_rows, write_rows

logger = logging.getLogger(__name__)
_CLITICS = {"él", "tú", "yo"}
_LEADING_APOSTROPHES = "'’‘‛"
_NEGATIVE_CONTRACTION_STEMS = frozenset(
    {
        "aren",
        "couldn",
        "daren",
        "didn",
        "doesn",
        "hadn",
        "hasn",
        "haven",
        "isn",
        "mightn",
        "mustn",
        "needn",
        "shan",
        "shouldn",
        "wasn",
        "weren",
        "wouldn",
    }
)


def is_detached_english_suffix(row):
    """Recognize spaCy contraction suffix tokens such as ``'s`` and ``’ll``."""
    return any(
        isinstance(row.get(key), str) and row[key].startswith(tuple(_LEADING_APOSTROPHES))
        for key in ("lemma", "form")
    )


def english_word_label(text):
    """Keep alphabetic tokens and normalize a terminal full stop in abbreviations."""
    if not isinstance(text, str):
        return None
    candidate = text.rstrip(".")
    return candidate if candidate and candidate.isalpha() else None


def is_negative_contraction_stem(row):
    """Remove the AUX fragments left after splitting ``wouldn't`` and peers."""
    return row.get("pos") in {"AUX", "PART"} and any(
        english_word_label(row.get(key, "")) in _NEGATIVE_CONTRACTION_STEMS for key in ("lemma", "form")
    )


def display_lemma(lemma, pos):
    if isinstance(lemma, str) and lemma.isalpha():
        return lemma
    words = lemma.split()
    if pos in {"VERB", "AUX"} and len(words) == 2 and words[0].isalpha() and words[1] in _CLITICS:
        return words[0]
    return None


def process(lemmas, forms, language="es"):
    if language == "en":
        labels = {
            (row["lemma"], row["pos"]): None
            if is_detached_english_suffix(row) or is_negative_contraction_stem(row)
            else english_word_label(row["lemma"])
            for row in lemmas
        }
        groups = defaultdict(list)
        for row in lemmas:
            label = labels[row["lemma"], row["pos"]]
            if label:
                groups[label, row["pos"]].append(row)
        clean_lemmas = []
        for (lemma, pos), group in groups.items():
            primary = next((row for row in group if row["lemma"] == lemma), group[0])
            merged = {**primary, "lemma": lemma, "count": sum(row["count"] for row in group)}
            observed = defaultdict(int)
            for row in group:
                for form, count in row.get("observed_forms", {}).items():
                    normalized = english_word_label(form)
                    if normalized:
                        observed[normalized] += count
            merged["observed_forms"] = dict(observed)
            clean_lemmas.append(merged)
        allowed = {(row["lemma"], row["pos"]) for row in clean_lemmas}
        form_groups = defaultdict(list)
        for row in forms:
            lemma = labels.get((row["lemma"], row["pos"]))
            form = (
                None
                if is_detached_english_suffix(row) or is_negative_contraction_stem(row)
                else english_word_label(row["form"])
            )
            if lemma and form and (lemma, row["pos"]) in allowed:
                form_groups[form, lemma, row["pos"]].append(row)
        clean_forms = []
        for (form, lemma, pos), group in form_groups.items():
            primary = next((row for row in group if row["form"] == form), group[0])
            merged = {**primary, "form": form, "lemma": lemma, "count": sum(row["count"] for row in group)}
            if any(row["form"] != form for row in group):
                merged["reference_frequency"] = get_reference_frequency(form, "en")
            clean_forms.append(merged)
        total = sum(row["count"] for row in clean_lemmas)
        cumulative = 0
        for rank, row in enumerate(
            sorted(clean_lemmas, key=lambda r: (-r["count"], r["lemma"], r["pos"])), 1
        ):
            cumulative += row["count"]
            row.update(
                rank=rank,
                share=row["count"] / total if total else 0.0,
                book_relative_frequency=row["count"] / total if total else 0.0,
                cumulative_coverage=cumulative / total if total else 0.0,
            )
        for rank, row in enumerate(
            sorted(clean_forms, key=lambda r: (-r["count"], r["form"], r["lemma"], r["pos"])), 1
        ):
            row.update(rank=rank, book_relative_frequency=row["count"] / total if total else 0.0)
        by_key = defaultdict(list)
        for row in clean_forms:
            by_key[row["lemma"], row["pos"]].append(row)
        for row in clean_lemmas:
            reference = sum(
                {
                    item["form"]: item.get("reference_frequency", 0.0)
                    for item in by_key[row["lemma"], row["pos"]]
                }.values()
            )
            row["reference_frequency"] = reference
            row["specificity"] = calculate_specificity(row["book_relative_frequency"], reference)
        return clean_lemmas, clean_forms
    labels = {(row["lemma"], row["pos"]): display_lemma(row["lemma"], row["pos"]) for row in lemmas}
    groups = defaultdict(list)
    for row in lemmas:
        label = labels[row["lemma"], row["pos"]]
        if label:
            groups[label, row["pos"]].append(row)
    clean_lemmas, id_map = [], {}
    for (lemma, pos), group in groups.items():
        primary = next((row for row in group if row["lemma"] == lemma), group[0])
        merged = {**primary, "lemma": lemma, "count": sum(row["count"] for row in group)}
        observed = defaultdict(int)
        for row in group:
            for form, count in row["observed_forms"].items():
                observed[form] += count
            id_map[row["id"]] = primary["id"]
        merged["observed_forms"] = dict(observed)
        clean_lemmas.append(merged)
    total = sum(row["count"] for row in clean_lemmas)
    cumulative = 0
    for rank, row in enumerate(sorted(clean_lemmas, key=lambda r: (-r["count"], r["lemma"], r["pos"])), 1):
        cumulative += row["count"]
        row["rank"] = rank
        row["share"] = row["book_relative_frequency"] = row["count"] / total if total else 0.0
        row["cumulative_coverage"] = cumulative / total if total else 0.0
    clean_forms = []
    for row in forms:
        label = labels.get((row["lemma"], row["pos"]))
        if label and row["form"].isalpha():
            clean_forms.append({**row, "lemma": label, "book_relative_frequency": row["count"] / total})
    clean_forms.sort(key=lambda r: (-r["count"], r["form"], r["lemma"], r["pos"]))
    for rank, row in enumerate(clean_forms, 1):
        row["rank"] = rank
    by_key = defaultdict(list)
    for row in clean_forms:
        by_key[row["lemma"], row["pos"]].append(row)
    for row in clean_lemmas:
        reference = sum(
            {item["form"]: item["reference_frequency"] for item in by_key[row["lemma"], row["pos"]]}.values()
        )
        row["reference_frequency"] = reference
        row["specificity"] = calculate_specificity(row["book_relative_frequency"], reference)
    return clean_lemmas, clean_forms


def run(lemma_source, form_source, lemma_target, form_target, language="es"):
    lemmas, forms = process(read_rows(lemma_source), read_rows(form_source), language)
    write_rows(lemma_target, lemmas)
    write_rows(form_target, forms)
    logger.info("Постобработка: лемм %d, словоформ %d.", len(lemmas), len(forms))
