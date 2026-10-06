import re
from collections import Counter
from dataclasses import replace

from src.cards.formatter import normalize_card_form
from src.cards.models import CardEntry
from src.grammar.gender_pairs import gender_pair_for_word, masculine_word
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
    pair_indexes = {}
    known = known_words or set()

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
        pair = (
            gender_pair_for_word(group["lemma"])
            if language == "es" and any(row["pos"] == "NOUN" for row in rows)
            else None
        )
        pair_known = pair and any(
            normalize_card_form(value) in known
            for value in (
                pair["masculine"], pair["feminine"],
                masculine_word(pair), pair["feminine"].removeprefix("la "),
            )
        )
        if (
            not any(r["id"] in selection.eligible_lemma_ids for r in rows)
            or normalize_card_form(group["lemma"]) in known
            or pair_known
        ):
            continue
        gs = [grammar.get(r["id"], {}) for r in rows]
        ts = [translations.get(r["id"], {}) for r in rows]
        observed = Counter()
        for row in rows:
            for form, count in (row.get("observed_forms") or {}).items():
                observed[normalize_card_form(form)] += count
        if pair:
            grammatical_forms = " / ".join(
                pair[key] for key in
                ("masculine", "feminine", "masculine_plural", "feminine_plural")
            )
            learning_form = pair["masculine"]
        else:
            grammatical_forms = (
                gs[0].get("grammar_forms", "")
                if len(rows) == 1 else joined(g.get("grammar_forms", "") for g in gs)
            )
            learning_form = (
                gs[0].get("learning_form", "") if len(rows) == 1
                else group["lemma"] if language == "en"
                else joined(g.get("learning_form", "") for g in gs)
            )
        value = CardEntry(
            lemma=group["lemma"],
            pos=", ".join(r["pos"] for r in rows),
            rank=group["rank"],
            grammatical_forms=grammatical_forms,
            learning_form=learning_form,
            ipa=ipa.get(masculine_word(pair) if pair else group["lemma"]) or "-",
            translation_ru=joined(t.get("ru") for t in ts) or "—",
            translation_en=joined(t.get("en") for t in ts) or "—",
            observed_forms=dict(observed),
            gender_pair=bool(pair),
        )
        if pair:
            key = masculine_word(pair)
            if key in pair_indexes:
                index = pair_indexes[key]
                previous = cards[index]
                combined_forms = Counter(previous.observed_forms)
                combined_forms.update(value.observed_forms)
                cards[index] = replace(
                    previous,
                    rank=min(previous.rank, value.rank),
                    pos=joined([previous.pos, value.pos]),
                    translation_ru=joined([previous.translation_ru, value.translation_ru]) or "—",
                    translation_en=joined([previous.translation_en, value.translation_en]) or "—",
                    observed_forms=dict(combined_forms),
                )
                continue
            pair_indexes[key] = len(cards)
        cards.append(value)
    cards.sort(key=lambda card: (card.rank, card.lemma))
    missing = {
        "IPA": sum(card.ipa == "-" for card in cards),
        "Russian translations": sum(card.translation_ru == "—" for card in cards),
        "observed forms": sum(not card.observed_forms for card in cards),
    }
    if language == "es":
        missing["English translations"] = sum(card.translation_en == "—" for card in cards)
    nonzero = {name: count for name, count in missing.items() if count}
    if nonzero:
        import logging

        logging.getLogger(__name__).info(
            "Карточки с заглушками/пропусками: %s.",
            ", ".join(f"{name}: {count}" for name, count in nonzero.items()),
        )
    return cards, selection
