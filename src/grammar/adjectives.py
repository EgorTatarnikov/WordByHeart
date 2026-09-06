from .nouns import plural


def paradigm(word, lexicon):
    if word in lexicon["adjectives"]:
        return lexicon["adjectives"][word]
    if word.endswith("o"):
        return [word, word[:-1] + "a", word + "s", word[:-1] + "as"]
    if word.endswith(("ante", "ente", "able", "ible", "ista")):
        return [word, plural(word)]
    return []


def enrich_adjective(entry, info, lexicon):
    forms = paradigm(entry["lemma"], lexicon)
    if not forms:
        info.review.append("Парадигма прилагательного требует словаря")
        return
    if any(f not in forms for f in entry["observed_forms"]):
        info.review.append("Парадигма не покрывает наблюдаемые формы: проверить лемму/апокопу")
    info.grammar_forms = " / ".join(dict.fromkeys(forms))
