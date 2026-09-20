"""Select entries once and dispatch to either Kaikki or the model."""

import logging

from src.config import MachineTranslationSettings
from src.models import Translation
from src.storage import read_rows, write_rows

from .selection import select_lemmas_by_cumulative_coverage

logger = logging.getLogger(__name__)


def prepare_entries(lemmas, forms, config):
    entries = []
    for kind, rows in (("lemma", lemmas), ("form", forms)):
        for row in rows:
            entry = {
                "id": row["id"],
                "kind": kind,
                "lemma": row["lemma"],
                "pos": row["pos"],
                "morph_variants": row["morph_variants"],
                "contexts": row["contexts"][: config.max_contexts],
            }
            if kind == "form":
                entry["form"] = row["form"]
            else:
                entry["observed_forms"] = dict(
                    sorted(row["observed_forms"].items(), key=lambda x: (-x[1], x[0]))[:10]
                )
            entries.append(entry)
    return entries


def run(
    lemma_source, form_source, target, cache_path, config, provider=None, language="es", machine_config=None,
    known_words=None,
):
    machine_config = machine_config or MachineTranslationSettings()
    lemmas, forms = read_rows(lemma_source), read_rows(form_source)
    selection = select_lemmas_by_cumulative_coverage(
        lemmas,
        forms,
        config.cumulative_coverage_limit,
        config.specificity_threshold,
        config.min_book_occurrences,
    )
    entries = prepare_entries(lemmas, forms, machine_config)
    eligible_ids = selection.eligible_lemma_ids | selection.eligible_form_ids
    eligible_entries = [entry for entry in entries if entry["id"] in eligible_ids]
    if known_words:
        from src.cards.formatter import normalize_card_form

        eligible_entries = [
            entry for entry in eligible_entries
            if normalize_card_form(entry["lemma"]) not in known_words
        ]
    logger.info(
        "Перевод: %s; выбрано %d лемм и %d словоформ; coverage %.2f%%.",
        "модель" if machine_config.enabled else "Kaikki",
        len(selection.eligible_lemma_ids),
        len(selection.eligible_form_ids),
        selection.actual_coverage * 100,
    )
    if machine_config.enabled:
        if machine_config.translate_examples:
            raise ValueError("machine_translation.translate_examples пока не реализован")
        from .openai_translator import translate_entries

        translated = translate_entries(eligible_entries, machine_config, cache_path, provider, language)
    else:
        from .kaikki import translate_entries

        translated = translate_entries(
            eligible_entries, cache_path.parent / "kaikki" / "dictionary.sqlite", language
        )
    by_id = {item.id: item for item in translated}
    write_rows(
        target,
        [
            by_id.get(
                entry["id"],
                Translation(
                    entry["id"],
                    error=(
                        "known word excluded"
                        if known_words and normalize_card_form(entry["lemma"]) in known_words
                        else "outside cumulative coverage limit"
                    ),
                    translation_eligible=False,
                ),
            )
            for entry in entries
        ],
    )
