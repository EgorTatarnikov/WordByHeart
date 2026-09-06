import importlib.metadata
import logging
from pathlib import Path

from filelock import FileLock

from src.config import load_config
from src.languages import get_profile
from src.manifest import DEPENDENCIES, Manifest
from src.storage import digest, file_hash

logger = logging.getLogger(__name__)

ARTIFACTS = {
    "preprocess": ["01_normalized.txt"],
    "nlp": ["02_occurrences.parquet"],
    "aggregate": ["03_lemmas.parquet", "03_forms.parquet"],
    "reference": ["03_reference_lemmas.parquet", "03_reference_forms.parquet"],
    "grammar": ["04_lemmas_grammar.parquet", "04_forms_grammar.parquet"],
    "ipa": ["05_ipa.parquet"],
    "translate": ["06_translations.parquet"],
    "postprocess": ["08_lemmas.parquet", "08_forms.parquet"],
    "validate": ["07_validation.parquet"],
    "cards": [],
}
CODE_PATHS = {
    "preprocess": ["preprocessing/loader.py", "preprocessing/normalizer.py"],
    "nlp": ["nlp/processor.py", "preprocessing/chunker.py"],
    "aggregate": ["aggregation", "nlp/token_filter.py"],
    "reference": ["reference_frequency"],
    "grammar": ["grammar"],
    "ipa": ["pronunciation", "cache.py"],
    "translate": ["translation", "cache.py"],
    "postprocess": ["postprocessing"],
    "validate": ["validation", "grammar/pos_mapping.py"],
    "export": ["export", "grammar/pos_mapping.py"],
    "cards": ["cards", "translation/selection.py"],
}
PACKAGES = {
    "preprocess": [],
    "nlp": [
        "spacy",
        "spacy-transformers",
        "spacy-curated-transformers",
        "curated-transformers",
        "curated-tokenizers",
        "torch",
    ],
    "aggregate": [],
    "reference": ["wordfreq"],
    "grammar": [],
    "ipa": ["phonemizer"],
    "translate": ["openai", "pydantic"],
    "postprocess": [],
    "validate": [],
    "export": ["openpyxl"],
    "cards": ["python-docx"],
}


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


class Pipeline:
    def __init__(self, config_path=Path("config.yaml"), source=None):
        self.config_path = Path(config_path).resolve()
        self.base = self.config_path.parent
        self.config = load_config(self.config_path)
        self.profile = get_profile(self.config.language)
        self.work, self.cache, self.output = [
            self.resolve(getattr(self.config.paths, key)) for key in ("work", "cache", "output")
        ]
        if self.config.grammar.lexicon:
            self.config.grammar.lexicon = str(self.resolve(self.config.grammar.lexicon))
        known_path = self.config.known_dictionary.path or f"my_dictionary_{self.config.language}.xlsx"
        self.known_dictionary_path = self.resolve(known_path)
        self.manifest = Manifest(self.work / "manifest.json")
        saved = self.manifest.data.get("source", {}).get("file")
        self.source = Path(source).resolve() if source else Path(saved) if saved else None
        self.outputs = {stage: [self.work / name for name in names] for stage, names in ARTIFACTS.items()}
        self.outputs["export"] = []
        if self.config.export.xlsx:
            self.outputs["export"].append(self.output / self.profile.export_filename)
        if self.config.export.csv:
            self.outputs["export"].extend(self.output / name for name in ("lemmas.csv", "forms.csv"))
        self.outputs["cards"] = (
            [self.output / self.config.cards.output_filename] if self.config.cards.enabled else []
        )

    def resolve(self, name):
        return (self.base / name).resolve()

    def snapshots(self):
        cfg = self.config.model_dump()
        configs = {
            "preprocess": {
                "preprocess": cfg["preprocess"],
                "source": {
                    "file": str(self.source),
                    "sha256": file_hash(self.source) if self.source and self.source.is_file() else "missing",
                },
            },
            "nlp": {
                "language": cfg["language"],
                "nlp": cfg["nlp"],
                "model_version": package_version(self.config.nlp.model),
            },
            "aggregate": {"aggregation": cfg["aggregation"], "filters": cfg["filters"]},
            "reference": {"language": self.profile.wordfreq_language},
            "grammar": {"language": cfg["language"], "grammar": cfg["grammar"]},
            "ipa": {"pronunciation": cfg["pronunciation"]},
            "translate": {
                "language": cfg["language"],
                "targets": self.profile.translation_targets,
                "translation": cfg["translation"],
            },
            "postprocess": {"language": cfg["language"]},
            "validate": {
                "validation": cfg["validation"],
                "language": cfg["language"],
                "enabled": {k: cfg[k]["enabled"] for k in ("grammar", "pronunciation", "translation")},
            },
            "export": {"language": cfg["language"], "export": cfg["export"], "output": str(self.output)},
            "cards": {
                "language": cfg["language"],
                "cards": cfg["cards"],
                "coverage": cfg["translation"]["cumulative_coverage_limit"],
                "specificity_threshold": cfg["translation"]["specificity_threshold"],
                "min_book_occurrences": cfg["translation"]["min_book_occurrences"],
                "output": str(self.output),
                "known_dictionary": cfg["known_dictionary"],
            },
        }
        if self.config.grammar.lexicon:
            path = Path(self.config.grammar.lexicon)
            configs["grammar"]["lexicon_hash"] = file_hash(path) if path.is_file() else "missing"
        template = self.resolve(self.config.cards.template)
        configs["cards"]["template_hash"] = file_hash(template) if template.is_file() else "missing"
        if self.config.known_dictionary.enabled:
            configs["cards"]["known_dictionary_hash"] = (
                file_hash(self.known_dictionary_path) if self.known_dictionary_path.is_file() else "missing"
            )
        if self.config.pronunciation.enabled:
            try:
                from phonemizer.backend import EspeakBackend

                configs["ipa"]["engine_version"] = str(EspeakBackend.version())
            except (ImportError, RuntimeError, OSError):
                configs["ipa"]["engine_version"] = "unavailable"
        root = Path(__file__).parent
        fingerprints = {}
        for stage, paths in CODE_PATHS.items():
            files = [root / f for f in ("models.py", "storage.py", "pipeline.py", "manifest.py")]
            for path in paths:
                full = root / path
                files.extend(
                    sorted(p for p in full.rglob("*") if p.suffix in {".py", ".json"})
                ) if full.is_dir() else files.append(full)
            versions = {p: package_version(p) for p in PACKAGES[stage] + ["pyarrow"]}
            configs[stage]["tool_versions"] = versions
            fingerprints[stage] = digest(
                {
                    "config": configs[stage],
                    "code": {str(p.relative_to(root)): file_hash(p) for p in files},
                    "packages": versions,
                }
            )
        return configs, fingerprints

    def status(self):
        configs, fingerprints = self.snapshots()
        source_ok = bool(self.source and self.source.is_file())
        result = {"source": ("OK" if source_ok else "MISSING", str(self.source or "не задан"))}
        if source_ok and self.manifest.data.get("source", {}).get("sha256") not in {
            None,
            file_hash(self.source),
        }:
            result["source"] = ("CHANGED", str(self.source))
        for stage in DEPENDENCIES:
            result[stage] = self.manifest.status(stage, configs, fingerprints, self.outputs)
        return result

    def run(self, stage, force=False):
        self.work.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.work / ".pipeline.lock"), timeout=0):
            self.manifest = Manifest(self.work / "manifest.json")
            if stage == "run-all":
                cached = []

                def log_cached():
                    nonlocal cached
                    if cached:
                        logger.info("Использованы сохранённые результаты: %s", ", ".join(cached))
                        cached = []

                for name in DEPENDENCIES:
                    result = self._run(name, force, quiet_cached=True, before_run=log_cached)
                    if result == "cached":
                        cached.append(name)
                log_cached()
            else:
                self._run(stage, force)

    def _run(self, stage, force=False, quiet_cached=False, before_run=None):
        if stage == "preprocess" and (not self.source or not self.source.is_file()):
            raise ValueError("Укажите существующий UTF-8 TXT: preprocess book.txt")
        configs, fingerprints = self.snapshots()
        for dependency in DEPENDENCIES[stage]:
            state, reason = self.manifest.status(dependency, configs, fingerprints, self.outputs)
            if state != "OK":
                # Allow the requested IPA -> export workflow to refresh cheap validation only.
                if stage == "export" and dependency == "validate":
                    self._run("validate")
                    configs, fingerprints = self.snapshots()
                else:
                    raise RuntimeError(
                        f"{stage}: зависимость {dependency} {state}: {reason}. Запустите {dependency} или run-all."
                    )
        state, reason = self.manifest.status(stage, configs, fingerprints, self.outputs)
        if state == "OK" and not force:
            if not quiet_cached:
                logger.info("%s: OK, используется сохранённый результат", stage)
            return "cached"
        if before_run:
            before_run()
        logger.info("%s: запуск (%s)", stage, "force" if force else reason)
        if stage == "preprocess":
            self.manifest.data["source"] = configs[stage]["source"]
        self.manifest.begin(stage, configs[stage], fingerprints[stage])
        try:
            metadata = self.execute(stage)
            _, after = self.snapshots()
            if after[stage] != fingerprints[stage]:
                raise RuntimeError("Вход/код стадии изменился во время выполнения; повторите запуск")
            self.manifest.complete(stage, self.outputs[stage], metadata)
        except Exception as exc:
            self.manifest.fail(stage, exc)
            raise
        return "ran"

    def data_paths(self):
        return {
            "lemmas": self.outputs["postprocess"][0],
            "forms": self.outputs["postprocess"][1],
            "lemma_grammar": self.outputs["grammar"][0],
            "form_grammar": self.outputs["grammar"][1],
            "ipa": self.outputs["ipa"][0],
            "translations": self.outputs["translate"][0],
        }

    def execute(self, stage):
        cfg, out = self.config, self.outputs[stage]
        if stage == "preprocess":
            from src.preprocessing.loader import run

            run(self.source, out[0], cfg.preprocess)
        elif stage == "nlp":
            from src.nlp.processor import run

            run(self.outputs["preprocess"][0], out[0], cfg.nlp)
        elif stage == "aggregate":
            from src.aggregation.aggregator import run

            run(self.outputs["nlp"][0], *out, cfg.aggregation, cfg.filters)
        elif stage == "reference":
            from src.reference_frequency.calculator import run

            run(*self.outputs["aggregate"], *out, self.profile.wordfreq_language)
        elif stage == "postprocess":
            from src.postprocessing.processor import run

            run(*self.outputs["reference"], *out, cfg.language)
        elif stage == "grammar":
            from src.grammar.enrichment import run

            run(*self.outputs["postprocess"], *out, cfg.grammar, cfg.language)
        elif stage == "ipa":
            from src.pronunciation.service import run

            run(*self.outputs["postprocess"], out[0], self.cache / "phonemes.sqlite", cfg.pronunciation)
        elif stage == "translate":
            from src.translation.openai_translator import run

            run(
                *self.outputs["postprocess"],
                out[0],
                self.cache / "translations.sqlite",
                cfg.translation,
                language=cfg.language,
            )
        elif stage == "validate":
            from src.validation.validator import run

            run(self.data_paths(), out[0], cfg)
        elif stage == "export":
            from src.export.excel_exporter import run

            run(
                {**self.data_paths(), "validation": self.outputs["validate"][0]},
                self.output,
                cfg.export,
                cfg.language,
            )
        elif stage == "cards":
            if not cfg.cards.enabled:
                return
            from src.cards.docx_renderer import run

            return run(
                self.data_paths(),
                self.resolve(cfg.cards.template),
                out[0],
                cfg.cards,
                cfg.translation,
                cfg.language,
                str(self.known_dictionary_path) if cfg.known_dictionary.enabled else None,
            )
