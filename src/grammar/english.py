"""Conservative English learning-form enrichment."""

from collections import defaultdict

from src.grammar.pos_mapping import POS_RU, format_morph
from src.models import GrammarInfo

IRREGULAR_NOUNS = {
    "child": "children",
    "person": "people",
    "man": "men",
    "woman": "women",
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
}
IRREGULAR_ADJECTIVES = {"good": ("better", "best"), "bad": ("worse", "worst"), "far": ("farther", "farthest")}
IRREGULAR_VERBS = {
    "be": ("am", "are", "is", "was", "were", "been", "being"),
    "go": ("goes", "went", "gone", "going"),
    "have": ("has", "had", "had", "having"),
    "do": ("does", "did", "done", "doing"),
    "say": ("says", "said", "said", "saying"),
    "make": ("makes", "made", "made", "making"),
    "come": ("comes", "came", "come", "coming"),
    "see": ("sees", "saw", "seen", "seeing"),
    "get": ("gets", "got", "got", "getting"),
    "know": ("knows", "knew", "known", "knowing"),
    "think": ("thinks", "thought", "thought", "thinking"),
    "take": ("takes", "took", "taken", "taking"),
    "give": ("gives", "gave", "given", "giving"),
    "find": ("finds", "found", "found", "finding"),
    "tell": ("tells", "told", "told", "telling"),
    "become": ("becomes", "became", "become", "becoming"),
    "leave": ("leaves", "left", "left", "leaving"),
    "feel": ("feels", "felt", "felt", "feeling"),
    "put": ("puts", "put", "put", "putting"),
    "bring": ("brings", "brought", "brought", "bringing"),
    "begin": ("begins", "began", "begun", "beginning"),
    "keep": ("keeps", "kept", "kept", "keeping"),
    "hold": ("holds", "held", "held", "holding"),
    "write": ("writes", "wrote", "written", "writing"),
    "stand": ("stands", "stood", "stood", "standing"),
    "hear": ("hears", "heard", "heard", "hearing"),
    "let": ("lets", "let", "let", "letting"),
    "mean": ("means", "meant", "meant", "meaning"),
    "set": ("sets", "set", "set", "setting"),
    "meet": ("meets", "met", "met", "meeting"),
    "run": ("runs", "ran", "run", "running"),
    "pay": ("pays", "paid", "paid", "paying"),
    "sit": ("sits", "sat", "sat", "sitting"),
    "speak": ("speaks", "spoke", "spoken", "speaking"),
    "lie": ("lies", "lay", "lain", "lying"),
    "lead": ("leads", "led", "led", "leading"),
    "read": ("reads", "read", "read", "reading"),
    "grow": ("grows", "grew", "grown", "growing"),
    "lose": ("loses", "lost", "lost", "losing"),
    "fall": ("falls", "fell", "fallen", "falling"),
    "send": ("sends", "sent", "sent", "sending"),
    "build": ("builds", "built", "built", "building"),
    "understand": ("understands", "understood", "understood", "understanding"),
    "draw": ("draws", "drew", "drawn", "drawing"),
    "break": ("breaks", "broke", "broken", "breaking"),
    "spend": ("spends", "spent", "spent", "spending"),
    "cut": ("cuts", "cut", "cut", "cutting"),
}
MODALS = {
    "can": ("can", "could"),
    "may": ("may", "might"),
    "must": ("must",),
    "shall": ("shall", "should"),
    "will": ("will", "would"),
}


def plural(word):
    if word in IRREGULAR_NOUNS:
        return IRREGULAR_NOUNS[word]
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("f"):
        return word[:-1] + "ves"
    if word.endswith("fe"):
        return word[:-2] + "ves"
    return word + "s"


def third_person(word):
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        return word + "es"
    return word + "s"


def past(word):
    if word.endswith("e"):
        return word + "d"
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ied"
    return word + "ed"


def ing(word):
    if word.endswith("ie"):
        return word[:-2] + "ying"
    if word.endswith("e") and not word.endswith(("ee", "ye", "oe")):
        return word[:-1] + "ing"
    return word + "ing"


def enrich(lemmas, forms, config):
    by_lemma = defaultdict(list)
    for row in forms:
        by_lemma[row["lemma"], row["pos"]].append(row)
    result = []
    for row in lemmas:
        word, info = row["lemma"], GrammarInfo(row["id"], learning_form=row["lemma"])
        if config.enabled:
            info.provenance = "English conservative rules + irregular lexicon"
            if row["pos"] == "NOUN":
                info.plural_form = plural(word)
                info.grammar_forms = f"{word} / {info.plural_form}"
            elif row["pos"] == "ADJ" and word in IRREGULAR_ADJECTIVES:
                info.grammar_forms = " / ".join((word, *IRREGULAR_ADJECTIVES[word]))
            elif row["pos"] in {"VERB", "AUX"}:
                if word in MODALS:
                    info.grammar_forms = " / ".join(MODALS[word])
                    info.review.append("Modal verb: incomplete paradigm")
                else:
                    forms_ = IRREGULAR_VERBS.get(
                        word, (third_person(word), past(word), past(word), ing(word))
                    )
                    info.infinitive = word
                    info.grammar_forms = " / ".join((word, *forms_))
        result.append(info)
    form_result = []
    for row in forms:
        info = GrammarInfo(row["id"])
        if config.enabled:
            info.morph_description = (
                POS_RU.get(row["pos"], row["pos"])
                + ": "
                + " | ".join(format_morph(m) for m in row["morph_variants"])
            )
            info.provenance = "observed UD morphology (variants separated by |)"
        form_result.append(info)
    return result, form_result
