"""Child process protocol: JSON progress on stdout, private logs on disk."""

import argparse
import contextlib
import json
import logging
import sys

from src.runtime import configure_logging

LABELS = {
    "preprocess": "Подготовка текста",
    "nlp": "Анализ текста",
    "aggregate": "Подсчёт слов",
    "reference": "Оценка частот",
    "postprocess": "Подготовка словаря",
    "grammar": "Грамматические формы",
    "ipa": "Транскрипция",
    "translate": "Перевод",
    "validate": "Проверка результатов",
    "export": "Таблицы",
    "cards": "Карточки",
}


def friendly_error(stage, exc):
    if isinstance(exc, UnicodeError):
        return "Не удалось прочитать текст. Сохраните TXT в кодировке UTF-8."
    if stage == "nlp":
        return "Не удалось выполнить анализ текста. Запустите INSTALL.bat для проверки NLP-модели."
    if stage == "ipa":
        return "Не удалось создать транскрипцию. Запустите INSTALL.bat для проверки eSpeak NG."
    if stage == "translate":
        return "Не удалось выполнить перевод через модель. Проверьте API key, доступ к модели и интернет."
    if isinstance(exc, PermissionError):
        return "Нет доступа к файлу. Закройте открытые таблицы и карточки и повторите запуск."
    return "Не удалось завершить обработку. Подробности сохранены в logs/wordbyheart.log."


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args(argv)
    handler = configure_logging()
    protocol = sys.stdout

    def send(event):
        protocol.write(json.dumps(event, ensure_ascii=True) + "\n")
        protocol.flush()

    active = ""

    def progress(stage, completed, total):
        nonlocal active
        active = stage
        send({"type": "progress", "label": LABELS[stage], "completed": completed, "total": total})

    try:
        from src.application import run_pipeline

        # tqdm and third-party prints must not corrupt the JSON channel.
        with contextlib.redirect_stdout(handler.stream), contextlib.redirect_stderr(handler.stream):
            pipeline = run_pipeline(args.config, args.source, on_progress=progress)
            files = {"folder": str(pipeline.output)}
            if pipeline.config.cards.enabled:
                files["cards"], files["list"] = map(str, pipeline.outputs["cards"])
            if pipeline.config.export.xlsx:
                files["table"] = str(pipeline.output / pipeline.profile.export_filename)
            elif pipeline.config.export.csv:
                files["table"] = str(pipeline.output / "lemmas.csv")
            from src.storage import read_rows

            lemmas = read_rows(pipeline.outputs["postprocess"][0])
            summary = f"Обработка завершена. Лемм: {len({row['lemma'] for row in lemmas})}."
            count = pipeline.manifest.data["stages"].get("cards", {}).get("selected_cards")
            if count is not None:
                summary += f" Карточек: {count}."
        send({"type": "done", "files": files, "summary": summary})
        return 0
    except Exception as exc:
        logging.getLogger(__name__).exception("Pipeline failed at %s", active)
        send({"type": "error", "message": friendly_error(active, exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
