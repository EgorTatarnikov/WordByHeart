def enrich_verb(entry, info, lexicon):
    word = entry["lemma"]
    base = word.removesuffix("se")
    info.infinitive = word
    info.conjugation_group = next(
        ("-" + ending for ending in ("ar", "er", "ir") if base.endswith(ending)), ""
    )
    info.regularity = lexicon["verbs"].get(word, lexicon["verbs"].get(base, "unknown"))
    if not info.conjugation_group:
        info.review.append("Лемма не распознана как инфинитив")
    if info.regularity == "unknown":
        info.review.append("Регулярность не подтверждена словарём")
