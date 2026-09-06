from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Paths(Settings):
    work: str = "data/work"
    cache: str = "data/cache"
    output: str = "data/output"


class Preprocess(Settings):
    strip_gutenberg: bool = False
    remove_page_numbers: bool = False
    remove_lines: list[str] = Field(default_factory=list)


class NLP(Settings):
    model: str = "es_dep_news_trf"
    batch_size: int = Field(16, ge=1)
    chunk_size: int = Field(5000, ge=100)


class Aggregation(Settings):
    max_contexts: int = Field(3, ge=1)


class Filters(Settings):
    include_proper_nouns: bool = True
    include_function_words: bool = True


class Grammar(Settings):
    enabled: bool = True
    lexicon: str | None = None


class Pronunciation(Settings):
    enabled: bool = True
    language: str = "es"
    batch_size: int = Field(128, ge=1)


class TranslationSettings(Settings):
    enabled: bool = True
    provider: str = "openai"
    model: str = ""
    batch_size: int = Field(30, ge=1, le=100)
    max_contexts: int = Field(3, ge=1)
    prompt_version: str = "1.0"
    translate_examples: bool = False
    max_attempts: int = Field(3, ge=1, le=10)
    timeout: float = Field(90, gt=0)
    cumulative_coverage_limit: float = 90.0
    specificity_threshold: float = Field(2.0, ge=0)
    min_book_occurrences: int = Field(3, ge=1)

    @field_validator("cumulative_coverage_limit")
    @classmethod
    def validate_cumulative_coverage_limit(cls, value: float) -> float:
        if not 0 < value <= 100:
            raise ValueError("translation.cumulative_coverage_limit must be > 0 and <= 100")
        return value


class Validation(Settings):
    max_translation_length: int = Field(200, ge=1)


class Export(Settings):
    xlsx: bool = True
    csv: bool = True
    font_size: int = Field(11, ge=8, le=24)
    context_width: int = Field(65, ge=20, le=120)


class Cards(Settings):
    enabled: bool = True
    template: str = "table.docx"
    output_filename: str = "spanish_cards.docx"
    rows: int = Field(8, ge=1)
    columns: int = Field(3, ge=1)
    cards_per_page: int = Field(24, ge=1)
    max_forms: int = Field(10, ge=1)
    front_font_size: int = Field(14, ge=6, le=36)
    back_font_size: int = Field(12, ge=6, le=36)
    long_forms_threshold: int = Field(90, ge=1)
    long_forms_font_size: int = Field(10, ge=6, le=36)
    long_translation_threshold: int = Field(35, ge=1)
    long_translation_font_size: int = Field(10, ge=6, le=36)


class KnownDictionary(Settings):
    enabled: bool = False
    path: str | None = None


class Config(Settings):
    language: str = "es"
    paths: Paths = Field(default_factory=Paths)
    preprocess: Preprocess = Field(default_factory=Preprocess)
    nlp: NLP = Field(default_factory=NLP)
    aggregation: Aggregation = Field(default_factory=Aggregation)
    filters: Filters = Field(default_factory=Filters)
    grammar: Grammar = Field(default_factory=Grammar)
    pronunciation: Pronunciation = Field(default_factory=Pronunciation)
    translation: TranslationSettings = Field(default_factory=TranslationSettings)
    validation: Validation = Field(default_factory=Validation)
    export: Export = Field(default_factory=Export)
    cards: Cards = Field(default_factory=Cards)
    known_dictionary: KnownDictionary = Field(default_factory=KnownDictionary)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        from src.languages import get_profile

        get_profile(value)
        return value


def load_config(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {})
