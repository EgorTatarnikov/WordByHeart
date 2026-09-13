import re
from collections import Counter

from src.cards.formatter import normalize_card_form
from src.cards.models import CardEntry
from src.lemma_groups import group_lemmas
from src.translation.selection import TranslationSelection, select_lemmas_by_cumulative_coverage


def select_cards(
    data: dict[str, list[dict]],
    coverage_limit: float,
    specificity_threshold: float = 2.0,
    min_book_occurrences: int = 3,
    language="es",
    known_words: set[str] | None = None,
) -> tuple[list[CardEntry], TranslationSelection]:
    lemmas = data["lemmas"]
    selection = select_lemmas_by_cumulative_coverage(
        lemmas, data["forms"], coverage_limit, specificity_threshold, min_book_occurrences
    )
    grammar = {row["id"]: row for row in data["lemma_grammar"]}
    ipa = {row["text"]: row.get("ipa", "") for row in data["ipa"]}
    translations = {row["id"]: row for row in data["translations"]}
    cards = []
    missing = {"IPA": 0, "Russian translations": 0, "observed forms": 0}
    if language == "es":
        missing["English translations"] = 0

    def joined(values, separator=", "):
        unique = {}
        for value in values:
            for part in re.split(r"[,;/|]", value or ""):
                part = part.strip()
                if part and part not in {"—", "-"}:
                    unique.setdefault(normalize_card_form(part), part)
        return separator.join(unique.values())

    for group in group_lemmas(lemmas, data["forms"]):
        rows = group["rows"]
        if not any(r["id"] in selection.eligible_lemma_ids for r in rows) or normalize_card_form(
            group["lemma"]
        ) in (known_words or set()):
            continue
        gs = [grammar.get(r["id"], {}) for r in rows]
        ts = [translations.get(r["id"], {}) for r in rows]
        observed = Counter()
        for row in rows:
            for form, count in (row.get("observed_forms") or {}).items():
                observed[normalize_card_form(form)] += count
        value = CardEntry(
            lemma=group["lemma"],
            pos=", ".join(r["pos"] for r in rows),
            rank=group["rank"],
            grammatical_forms=(
                gs[0].get("grammar_forms", "")
                if len(rows) == 1
                else joined(g.get("grammar_forms", "") for g in gs)
            ),
            learning_form=(
                gs[0].get("learning_form", "")
                if len(rows) == 1
                else group["lemma"]
                if language == "en"
                else joined(g.get("learning_form", "") for g in gs)
            ),
            ipa=ipa.get(group["lemma"]) or "-",
            translation_ru=joined(t.get("ru") for t in ts) or "—",
            translation_en=joined(t.get("en") for t in ts) or "—",
            observed_forms=dict(observed),
        )
        if value.ipa == "-":
            missing["IPA"] += 1
        if value.translation_ru == "—":
            missing["Russian translations"] += 1
        if language == "es" and value.translation_en == "—":
            missing["English translations"] += 1
        if not value.observed_forms:
            missing["observed forms"] += 1
        cards.append(value)
    nonzero = {name: count for name, count in missing.items() if count}
    if nonzero:
        import logging

        logging.getLogger(__name__).info(
            "Карточки с заглушками/пропусками: %s.",
            ", ".join(f"{name}: {count}" for name, count in nonzero.items()),
        )
    return cards, selection
