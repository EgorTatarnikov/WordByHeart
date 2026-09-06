from .pos_mapping import parse_morph


def plural(word, overrides=None):
    override = (overrides or {}).get(word, {})
    if "plural" in override:
        return override["plural"] or ""
    # Deliberately narrow: consonant stress changes and stressed vowels need a dictionary.
    if word.endswith(tuple("aeiou")):
        return word + "s"
    if word.endswith("z") and not any(c in word for c in "áéíóú"):
        return word[:-1] + "ces"
    if word.endswith(("ión", "ón")):
        return word[:-2] + "ones"
    if word.endswith(("dad", "tad", "or", "al", "el")) and not any(c in word for c in "áéíóú"):
        return word + "es"
    return ""


def enrich_noun(entry, info, lexicon, observed):
    word = entry["lemma"]
    override = lexicon["nouns"].get(word, {})
    genders = {parse_morph(m).get("Gender") for m in entry["morph_variants"]} - {None}
    gender = override.get("gender") or (next(iter(genders)) if len(genders) == 1 else "")
    if genders and override.get("gender") and genders != {gender}:
        info.review.append("Род словаря противоречит наблюдаемой морфологии")
    if gender not in {"Fem", "Masc"}:
        info.review.append("Род неизвестен или неоднозначен")
        return
    info.grammatical_gender = "женский" if gender == "Fem" else "мужской"
    article = "la" if gender == "Fem" else "el"
    if gender == "Fem" and word.startswith(("a", "á", "ha", "há")) and "singular_article" not in override:
        info.review.append("Нужна проверка ударного a/ha для выбора артикля")
        return
    if override.get("plural_only"):
        info.review.append("Pluralia tantum: учебная форма требует проверки")
        return
    article = override.get("singular_article", article)
    info.learning_form = f"{article} {word}"
    generated = plural(word, lexicon["nouns"])
    observed_plurals = {
        f["form"]
        for f in observed
        if any(parse_morph(m).get("Number") == "Plur" for m in f["morph_variants"])
    }
    if generated and observed_plurals and generated not in observed_plurals:
        info.review.append("Plural противоречит наблюдаемым формам")
        generated = ""
    if not generated and len(observed_plurals) == 1 and "plural" not in override:
        generated = next(iter(observed_plurals))
        info.provenance += "; plural from observed morphology"
    if generated:
        info.plural_form = f"{'las' if gender == 'Fem' else 'los'} {generated}"
    else:
        info.review.append("Plural не определён надёжно")
    info.grammar_forms = " / ".join(filter(None, [info.learning_form, info.plural_form]))
