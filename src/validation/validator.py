import logging
import re
from collections import Counter, defaultdict

from src.grammar.pos_mapping import POS_RU
from src.models import ValidationIssue
from src.storage import read_rows, write_rows

logger = logging.getLogger(__name__)


class Validator:
    def validate(self, lemmas, forms, grammar, ipa, translations, config):
        issues = []

        def add(id, category, message, severity="review"):
            issues.append(ValidationIssue(id, category, severity, message))

        for row in lemmas:
            if not row["lemma"]:
                add(row["id"], "nlp", "Пустая лемма", "error")
            if row["pos"] not in POS_RU or row["pos"] == "X":
                add(row["id"], "nlp", f"Неизвестный POS: {row['pos']}")
            if not row["lemma"].isalpha():
                add(row["id"], "nlp", "Неалфавитный токен: число, символ или OCR")
            if row["count"] == 1 and (
                len(row["lemma"]) > 20 or row["pos"] == "X" or not row["lemma"].isalpha()
            ):
                add(row["id"], "nlp", "Подозрительная одноразовая лемма")
            if len(row["lemma"]) > 40:
                add(row["id"], "nlp", "Подозрительно длинная лемма")
        by_form = defaultdict(list)
        for row in forms:
            by_form[row["form"]].append(row)
        for form, rows in by_form.items():
            if len({(r["lemma"], r["pos"]) for r in rows}) > 1:
                for row in rows:
                    add(
                        row["id"],
                        "ambiguity",
                        f"{form}: несколько lemma/POS; возможна нормальная омонимия",
                        "info",
                    )
        expected = {r["id"] for r in lemmas + forms}
        for category, rows in (("grammar", grammar), ("translation", translations)):
            ids = [r["id"] for r in rows]
            if len(ids) != len(set(ids)):
                add("", category, "Дублирующиеся IDs", "error")
            for id in sorted(expected - set(ids)):
                add(id, category, "Отсутствующий ID", "error")
            for id in sorted(set(ids) - expected):
                add(id, category, "Неизвестный ID", "error")
        if config.grammar.enabled:
            for row in grammar:
                for message in row["review"]:
                    add(row["id"], "grammar", message)
        if config.pronunciation.enabled:
            by_text = {r["text"]: r for r in ipa}
            for row in lemmas + forms:
                value = by_text.get(row.get("form", row["lemma"]), {})
                if value.get("error") or not value.get("ipa"):
                    add(row["id"], "ipa", value.get("error") or "Отсутствует IPA")
                elif re.search(r"[0-9]|\([a-z-]+\)", value["ipa"]):
                    add(row["id"], "ipa", "Подозрительная IPA")
        if config.translation.enabled:
            for row in translations:
                if not row.get("translation_eligible", True):
                    continue
                for lang in ("ru", "en") if config.language == "es" else ("ru",):
                    value = row.get(lang, "")
                    if not value.strip():
                        add(row["id"], "translation", f"Пустой {lang}", "error")
                    elif len(value) > config.validation.max_translation_length or any(
                        s in value for s in ("```", "**", "# ", "[", "\n")
                    ):
                        add(row["id"], "translation", f"{lang}: Markdown или длинное объяснение")
                    elif (lang == "ru" and not re.search(r"[а-яА-ЯёЁ]", value)) or (
                        lang == "en" and re.search(r"[а-яА-ЯёЁ]", value)
                    ):
                        add(row["id"], "translation", f"{lang}: проверить язык перевода")
        return issues


def run(paths, target, config):
    rows = {key: read_rows(value) for key, value in paths.items()}
    issues = Validator().validate(
        rows["lemmas"],
        rows["forms"],
        rows["lemma_grammar"] + rows["form_grammar"],
        rows["ipa"],
        rows["translations"],
        config,
    )
    write_rows(target, issues, columns=["id", "category", "severity", "message"])
    by_severity = Counter(issue.severity for issue in issues)
    summary = ", ".join(
        f"{severity}: {by_severity[severity]}"
        for severity in ("error", "review", "info")
        if by_severity[severity]
    )
    logger.info("Проверка: %d замечаний%s.", len(issues), f" ({summary})" if summary else "")
