from src.cards.formatter import normalize_card_form
from src.cards.models import CardEntry
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
    for lemma in sorted(lemmas, key=lambda row: row["rank"]):
        if lemma["id"] not in selection.eligible_lemma_ids or normalize_card_form(lemma["lemma"]) in (
            known_words or set()
        ):
            continue
        g = grammar.get(lemma["id"], {})
        t = translations.get(lemma["id"], {})
        value = CardEntry(
            lemma=lemma["lemma"],
            pos=lemma["pos"],
            rank=lemma["rank"],
            grammatical_forms=g.get("grammar_forms", ""),
            learning_form=g.get("learning_form", ""),
            ipa=ipa.get(lemma["lemma"]) or "-",
            translation_ru=t.get("ru") or "—",
            translation_en=t.get("en") or "—",
            observed_forms=lemma.get("observed_forms") or {},
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
