from collections import defaultdict

from src.storage import read_rows, write_rows


def get_reference_frequency(form: str, language="es", lookup=None) -> float:
    if lookup is None:
        from wordfreq import word_frequency

        lookup = word_frequency
    return float(lookup(form, language))


def calculate_specificity(book_frequency: float, reference_frequency: float) -> float:
    return book_frequency / max(reference_frequency, 1e-12)


def enrich(lemmas, forms, language="es", lookup=None):
    total = sum(row["count"] for row in lemmas)
    cache = {}
    for row in forms:
        form = row["form"]
        if form not in cache:
            cache[form] = get_reference_frequency(form, language, lookup)
        row["book_relative_frequency"] = row["count"] / total if total else 0.0
        row["reference_frequency"] = cache[form]
    by_key = defaultdict(list)
    for row in forms:
        by_key[row["lemma"], row["pos"]].append(row)
    for row in lemmas:
        row["book_relative_frequency"] = row["count"] / total if total else 0.0
        seen = {form["form"] for form in by_key[row["lemma"], row["pos"]]}
        row["reference_frequency"] = sum(cache[form] for form in seen)
        row["specificity"] = calculate_specificity(row["book_relative_frequency"], row["reference_frequency"])
    return lemmas, forms


def run(lemma_source, form_source, lemma_target, form_target, language="es"):
    lemmas, forms = enrich(read_rows(lemma_source), read_rows(form_source), language)
    write_rows(lemma_target, lemmas)
    write_rows(form_target, forms)
