POS_RU = {
    "NOUN": "существительное",
    "VERB": "глагол",
    "ADJ": "прилагательное",
    "ADV": "наречие",
    "PRON": "местоимение",
    "DET": "определитель / артикль",
    "ADP": "предлог",
    "AUX": "вспомогательный глагол",
    "PROPN": "имя собственное",
    "CCONJ": "сочинительный союз",
    "SCONJ": "подчинительный союз",
    "PART": "частица",
    "NUM": "числительное",
    "INTJ": "междометие",
    "SYM": "символ",
    "X": "неизвестно",
}

MORPH = {
    "Gender": {"Fem": "женский род", "Masc": "мужской род", "Com": "общий род"},
    "Number": {"Sing": "единственное число", "Plur": "множественное число"},
    "Person": {"1": "1 лицо", "2": "2 лицо", "3": "3 лицо"},
    "Mood": {"Ind": "Indicativo", "Sub": "Subjuntivo", "Imp": "Imperativo", "Cnd": "Condicional"},
    "Tense": {
        "Pres": "Presente",
        "Past": "Pretérito",
        "Imp": "Imperfecto",
        "Fut": "Futuro",
        "Pqp": "Pluscuamperfecto",
    },
    "VerbForm": {"Inf": "инфинитив", "Fin": "личная форма", "Ger": "герундий", "Part": "причастие"},
    "Definite": {"Def": "определённый", "Ind": "неопределённый"},
    "PronType": {
        "Art": "артикль",
        "Prs": "личное",
        "Rel": "относительное",
        "Int": "вопросительное",
        "Dem": "указательное",
        "Ind": "неопределённое",
        "Neg": "отрицательное",
        "Tot": "обобщающее",
    },
    "Polarity": {"Neg": "отрицание"},
    "Reflex": {"Yes": "возвратность"},
}


def parse_morph(raw):
    return dict(part.split("=", 1) for part in raw.split("|") if "=" in part)


def format_morph(raw):
    result = []
    for key, values in parse_morph(raw).items():
        result.append(
            " / ".join(MORPH.get(key, {}).get(value, f"{key}={value}") for value in values.split(","))
        )
    return ", ".join(result)
