"""Offline diagnostic run; saves results only in a fresh verification directory."""
import json
import tempfile
from pathlib import Path

from src.config import load_config
from src.gui.configuration import save_config
from src.languages.installation import language_is_installed
from src.pipeline import Pipeline
from src.preprocessing.loader import read_text_auto
from src.runtime import prepare_environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    prepare_environment()
    base = ROOT / "logs" / "verification"
    base.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="functional-", dir=base))
    report = {"directory": str(output), "encoding": {}, "languages": {}, "pipelines": {}}
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-32", "utf-16-le", "cp1252", "cp850"):
        text = "El niño caminó por la estación."
        source = output / (encoding + ".txt")
        source.write_bytes(text.encode(encoding))
        decoded, detected = read_text_auto(source)
        report["encoding"][encoding] = {"correct": decoded == text, "detected": detected}
    for language in ("en", "es"):
        report["languages"][language] = language_is_installed(ROOT, language)
        cfg = load_config(ROOT / "config" / f"demo_{language}.yaml")
        cfg.paths.work = str(output / language / "work")
        cfg.paths.output = str(output / language / "output")
        cfg.paths.cache = str(ROOT / "data" / "cache")
        cfg.cards.template = str(ROOT / "table.docx")
        cfg.machine_translation.enabled = False
        cfg.known_dictionary.enabled = False
        source = output / f"book_{language}.txt"
        sentence = "The dog watches the house. The dog runs home. " if language == "en" else "El perro mira la casa. El perro corre a casa. "
        source.write_text(sentence * 5, encoding="utf-8")
        config = output / f"run_{language}.yaml"
        save_config(config, cfg)
        try:
            pipeline = Pipeline(config, source)
            pipeline.run("run-all", on_progress=lambda stage, done, total: print(language, stage, done, total, flush=True))
            report["pipelines"][language] = {"ok": True, "cards": pipeline.manifest.data["stages"]["cards"].get("selected_cards"), "files": [p.name for p in Path(cfg.paths.output).iterdir()]}
        except Exception as exc:
            report["pipelines"][language] = {"ok": False, "error": str(exc)}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
