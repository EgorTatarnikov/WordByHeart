"""Conservative English contractions for book preprocessing.

Only unambiguous expansions belong in CONTRACTIONS_MAP. Unknown 's and
'll endings are removed as requested; ambiguous 'd and ain't stay unchanged.
Call expand_contractions(text) before tokenization for English books.
"""

import re


CONTRACTIONS_MAP = {
    "aren't": "are not",
    "can't": "can not",
    "couldn't": "could not",
    "couldn't've": "could not have",
    "daren't": "dare not",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hadn't": "had not",
    "hasn't": "has not",
    "haven't": "have not",
    "isn't": "is not",
    "mightn't": "might not",
    "mightn't've": "might not have",
    "mustn't": "must not",
    "needn't": "need not",
    "oughtn't": "ought not",
    "shan't": "shall not",
    "shouldn't": "should not",
    "shouldn't've": "should not have",
    "wasn't": "was not",
    "weren't": "were not",
    "won't": "will not",
    "wouldn't": "would not",
    "wouldn't've": "would not have",
    "i'm": "i am",
    "you're": "you are",
    "we're": "we are",
    "they're": "they are",
    "how're": "how are",
    "what're": "what are",
    "where're": "where are",
    "who're": "who are",
    "that're": "that are",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "who've": "who have",
    "how've": "how have",
    "could've": "could have",
    "might've": "might have",
    "must've": "must have",
    "should've": "should have",
    "would've": "would have",
    "i'd've": "i would have",
    "you'd've": "you would have",
    "he'd've": "he would have",
    "she'd've": "she would have",
    "we'd've": "we would have",
    "they'd've": "they would have",
}

_WORD = re.compile(r"[^\W\d_]+(?:['’‘ʼ][^\W\d_]+)*", re.UNICODE)
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def expand_contractions(text: str) -> str:
    """Expand known forms; strip unknown 's/'ll, preserving punctuation.

    Examples: wasn't -> was not; you'll -> you; father's -> father.
    Other ambiguous endings (he'd) and unknown forms remain unchanged.
    """
    def replace(match: re.Match) -> str:
        original = match.group()
        key = original.translate(_APOSTROPHES).lower()
        replacement = CONTRACTIONS_MAP.get(key)
        if replacement is None:
            if key.endswith("'s"):
                return original[:-2]
            if key.endswith("'ll"):
                return original[:-3]
            return original
        if original.isupper():
            return replacement.upper()
        if original[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]
        # The English pronoun I is always capitalized.
        return re.sub(r"\bi\b", "I", replacement)

    return _WORD.sub(replace, text)
