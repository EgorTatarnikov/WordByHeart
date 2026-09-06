FUNCTION_POS = {"DET", "ADP", "CCONJ", "SCONJ", "PRON", "AUX", "ADV", "PART"}


def include(row, config) -> bool:
    if row["is_punct"] or row["is_space"] or row["pos"] in {"PUNCT", "SPACE"}:
        return False
    if not config.include_proper_nouns and row["pos"] == "PROPN":
        return False
    return config.include_function_words or row["pos"] not in FUNCTION_POS
