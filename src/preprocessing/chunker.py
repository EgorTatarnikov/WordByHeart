import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    chunk_id: int
    paragraph_id: int
    start_char: int
    split_sentence: bool = False


def chunks(text: str, size: int):
    """Prefer paragraph/sentence boundaries; never split a word, even if oversized."""
    chunk_id = 0
    for paragraph_id, match in enumerate(re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\s*\Z)", text, re.DOTALL)):
        paragraph = match.group()
        start = 0
        while start < len(paragraph):
            stop = min(start + size, len(paragraph))
            split = False
            if stop < len(paragraph):
                boundaries = list(re.finditer(r"[.!?…][\"»”’']*\s+", paragraph[start:stop]))
                if boundaries:
                    stop = start + boundaries[-1].end()
                else:
                    spaces = list(re.finditer(r"\s+", paragraph[start:stop]))
                    if spaces:
                        stop = start + spaces[-1].end()
                    else:
                        tail = re.search(r"\s+", paragraph[stop:])
                        stop = stop + tail.end() if tail else len(paragraph)
                    split = True
            yield Chunk(paragraph[start:stop], chunk_id, paragraph_id, match.start() + start, split)
            chunk_id += 1
            start = stop
