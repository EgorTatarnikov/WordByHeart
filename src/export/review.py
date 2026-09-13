"""Plain-language view of validation results; diagnostics remain in Parquet."""

from src.grammar.pos_mapping import POS_RU

REVIEW_COLUMNS = ["Слово", "Часть речи", "Статус", "Что проверить", "Что сделать"]

_GRAMMAR = {
    "Modal verb: incomplete paradigm": "Не все формы модального глагола определены",
    "Лемма не распознана как инфинитив": "Не удалось определить начальную форму глагола",
    "Регулярность не подтверждена словарём": "Не определено, изменяется ли глагол по правилу",
    "Парадигма прилагательного требует словаря": "Не все формы прилагательного определены",
    "Парадигма не покрывает наблюдаемые формы: проверить лемму/апокопу": "Формы прилагательного не совпадают с формами в книге",
    "Род словаря противоречит наблюдаемой морфологии": "Род слова в словаре и в тексте различается",
    "Род неизвестен или неоднозначен": "Не удалось однозначно определить род слова",
    "Нужна проверка ударного a/ha для выбора артикля": "Нужно уточнить артикль перед ударным a/ha",
    "Pluralia tantum: учебная форма требует проверки": "Слово употребляется во множественном числе",
    "Plural противоречит наблюдаемым формам": "Множественное число не совпадает с формой в книге",
    "Plural не определён надёжно": "Не удалось надёжно определить множественное число",
}


def describe(issue):
    category, message = issue["category"], issue["message"]
    if message in {"Дублирующиеся IDs", "Отсутствующий ID", "Неизвестный ID"}:
        area = {"grammar": "грамматических данных", "translation": "переводов"}.get(category, "данных")
        return (
            f"Неполный или несогласованный набор {area}",
            "Повторите обработку; если проблема останется, сообщите разработчику.",
        )
    if category == "ipa":
        problem = (
            "Транскрипция выглядит необычно"
            if message == "Подозрительная IPA"
            else "Не удалось получить транскрипцию"
        )
        return problem, "Сверьте произношение со словарём."
    if category == "translation":
        language = "английский" if message.startswith(("en:", "Пустой en")) else "русский"
        if message.startswith("Пустой"):
            problem = f"Отсутствует перевод на {language}"
        elif "Markdown" in message:
            problem = f"Перевод на {language} слишком длинный или содержит лишнее оформление"
        else:
            problem = f"Возможно, перевод выполнен не на {language} язык"
        return problem, "Проверьте перевод по примеру из книги и уточните его перед изучением."
    if category == "grammar":
        return _GRAMMAR.get(
            message, "Грамматические формы требуют проверки"
        ), "Сверьте формы слова со словарём и примером из книги."
    if category == "nlp":
        problem = (
            "Не удалось определить часть речи"
            if message.startswith("Неизвестный POS")
            else "Не удалось определить начальную форму слова"
            if message == "Пустая лемма"
            else "Возможно, слово распознано неверно"
        )
        return problem, "Сверьте слово с исходным текстом: возможна опечатка или ошибка распознавания."
    return (
        "Результат обработки требует проверки",
        "Сверьте запись со словарём; при необходимости сообщите разработчику.",
    )


def make_review_rows(data):
    entries = {r["id"]: r for r in data["lemmas"] + data["forms"]}
    rows, seen = [], set()
    for issue in sorted(data["validation"], key=lambda r: (r["severity"] != "error", r["id"], r["message"])):
        if issue["severity"] == "info":
            continue
        entry = entries.get(issue["id"], {})
        problem, action = describe(issue)
        row = (
            entry.get("form", entry.get("lemma")) or "Весь словарь",
            POS_RU.get(entry.get("pos"), "—"),
            "Ошибка" if issue["severity"] == "error" else "Нужно проверить",
            problem,
            action,
        )
        if row not in seen:
            rows.append(list(row))
            seen.add(row)
    return rows or [["—", "—", "Замечаний нет", "Нет замечаний, требующих ручной проверки.", "—"]]
