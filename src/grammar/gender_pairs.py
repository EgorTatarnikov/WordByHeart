"""Curated Spanish noun forms used for learning cards."""

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path


def _key(word):
    return unicodedata.normalize("NFC", word).casefold()


@lru_cache(maxsize=1)
def gender_pairs():
    path = Path(__file__).with_name("spanish_gender_pairs.tsv")
    pairs = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            for field, article in (("masculine", "el "), ("feminine", "la ")):
                word = row[field].removeprefix(article)
                key = _key(word)
                if key in pairs and pairs[key] != row:
                    raise ValueError(f"Испанское слово встречается в нескольких парах рода: {word}")
                pairs[key] = row
    return pairs


def gender_pair_for_word(word):
    return gender_pairs().get(_key(word))


def masculine_word(pair):
    return pair["masculine"].removeprefix("el ")
