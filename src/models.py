from dataclasses import dataclass, field


@dataclass
class Occurrence:
    original_text: str
    normalized_form: str
    lemma: str
    pos: str
    morph: str
    is_alpha: bool
    is_punct: bool
    is_space: bool
    context: str
    chunk_id: int
    paragraph_id: int
    sentence_id: int
    token_index: int


@dataclass
class LemmaEntry:
    id: str
    lemma: str
    pos: str
    count: int
    observed_forms: dict[str, int]
    contexts: list[str]
    morph_variants: list[str]
    chunk_count: int


@dataclass
class FormEntry:
    id: str
    form: str
    lemma: str
    pos: str
    count: int
    morph_variants: list[str]
    contexts: list[str]
    original_forms: list[str]


@dataclass
class GrammarInfo:
    id: str
    learning_form: str = ""
    grammatical_gender: str = ""
    plural_form: str = ""
    grammar_forms: str = ""
    infinitive: str = ""
    conjugation_group: str = ""
    regularity: str = ""
    morph_description: str = ""
    provenance: str = ""
    review: list[str] = field(default_factory=list)


@dataclass
class Pronunciation:
    text: str
    language: str
    ipa: str = ""
    error: str = ""


@dataclass
class Translation:
    id: str
    ru: str = ""
    en: str = ""
    error: str = ""
    translation_eligible: bool = True


@dataclass
class ValidationIssue:
    id: str
    category: str
    severity: str
    message: str


@dataclass
class PipelineStageState:
    completed: bool
    fingerprint: str
    config: dict
    config_hash: str
    outputs: dict[str, str]
    generation: str
    dependencies: dict[str, str]
    completed_at: str = ""
    error: str = ""
