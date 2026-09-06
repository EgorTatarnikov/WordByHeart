from typing import Protocol


class Translator(Protocol):
    def translate(self, entries: list[dict]) -> list[dict]: ...
