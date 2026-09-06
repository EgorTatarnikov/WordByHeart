import csv
import logging
import math
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.grammar.pos_mapping import POS_RU
from src.storage import atomic_path, read_rows

logger = logging.getLogger(__name__)

LEMMA_COLUMNS = [
    "Ранг",
    "Лемма",
    "Учебная форма",
    "Суммарное число вхождений",
    "Доля от всех слов",
    "Кумулятивное покрытие",
    "Относительная частота в книге",
    "Частота Wordfreq",
    "Специфичность",
    "Транскрипция",
    "Часть речи",
    "Род",
    "Грамматические формы",
    "Инфинитив",
    "Группа спряжения",
    "Регулярность",
    "Словоформы в книге",
    "Перевод на русский",
    "Перевод на английский",
    "Пример из книги",
    "Количество контекстных блоков",
]
FORM_COLUMNS = [
    "Ранг",
    "Словоформа",
    "Число вхождений",
    "Относительная частота в книге",
    "Частота Wordfreq",
    "Транскрипция",
    "Лемма",
    "Часть речи",
    "Грамматические признаки",
    "Перевод на русский",
    "Перевод на английский",
    "Пример из книги",
]
REVIEW_COLUMNS = ["ID", "Категория", "Уровень", "Описание", "Запись", "Лемма", "POS"]


def make_tables(data):
    lg = {r["id"]: r for r in data["lemma_grammar"]}
    fg = {r["id"]: r for r in data["form_grammar"]}
    ipa = {r["text"]: f"/{r['ipa']}/" if r["ipa"] else "" for r in data["ipa"]}
    tr = {r["id"]: r for r in data["translations"]}
    lemma_rows, form_rows = [], []
    for r in sorted(data["lemmas"], key=lambda r: (-r["count"], r["lemma"], r["pos"])):
        g, t = lg[r["id"]], tr[r["id"]]
        observed = sorted(r["observed_forms"].items(), key=lambda x: (-x[1], x[0]))
        lemma_rows.append(
            [
                r["rank"],
                r["lemma"],
                g["learning_form"],
                r["count"],
                r["share"],
                r["cumulative_coverage"],
                r.get("book_relative_frequency", r["share"]),
                r.get("reference_frequency", 0.0),
                r.get("specificity", 0.0),
                ipa.get(r["lemma"], ""),
                POS_RU.get(r["pos"], r["pos"]),
                g["grammatical_gender"],
                g["grammar_forms"],
                g["infinitive"],
                g["conjugation_group"],
                g["regularity"],
                ", ".join(f"{f} ({n})" for f, n in observed),
                t["ru"],
                t["en"],
                r["contexts"][0] if r["contexts"] else "",
                r["chunk_count"],
            ]
        )
    for r in sorted(data["forms"], key=lambda r: (-r["count"], r["form"], r["lemma"], r["pos"])):
        g, t = fg[r["id"]], tr[r["id"]]
        form_rows.append(
            [
                r["rank"],
                r["form"],
                r["count"],
                r.get("book_relative_frequency", 0.0),
                r.get("reference_frequency", 0.0),
                ipa.get(r["form"], ""),
                r["lemma"],
                POS_RU.get(r["pos"], r["pos"]),
                g["morph_description"],
                t["ru"],
                t["en"],
                r["contexts"][0] if r["contexts"] else "",
            ]
        )
    entries = {r["id"]: r for r in data["lemmas"] + data["forms"]}
    review_rows = []
    for r in data["validation"]:
        entry = entries.get(r["id"], {})
        review_rows.append(
            [
                r["id"],
                r["category"],
                r["severity"],
                r["message"],
                entry.get("form", entry.get("lemma", "")),
                entry.get("lemma", ""),
                entry.get("pos", ""),
            ]
        )
    return [
        ("Леммы", LEMMA_COLUMNS, lemma_rows),
        ("Словоформы", FORM_COLUMNS, form_rows),
        ("Проверка", REVIEW_COLUMNS, review_rows),
    ]


def clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, str):
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
        if len(value) > 32767:
            logger.warning("Excel: текст длиннее лимита ячейки; полный текст остаётся в Parquet")
            value = value[:32764] + "..."
    return value


def write_excel(target, tables, config):
    book = Workbook()
    book.remove(book.active)
    for name, headers, rows in tables:
        if len(rows) > 1048575:
            raise ValueError(f"{name}: превышен лимит строк Excel")
        sheet = book.create_sheet(name)
        sheet.append(headers)
        widths = []
        for col, header in enumerate(headers, 1):
            width = (
                config.context_width
                if "Пример" in header
                else 48
                if header
                in {"Словоформы в книге", "Грамматические формы", "Грамматические признаки", "Описание"}
                else 26
            )
            widths.append(width)
            sheet.column_dimensions[get_column_letter(col)].width = width
        for values in rows:
            sheet.append([clean(v) for v in values])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        sheet.sheet_view.zoomScale = 85
        for row in sheet:
            line_count = 1
            for cell in row:
                if isinstance(cell.value, str):
                    # Book text and API output must never become executable Excel formulas.
                    cell.data_type = "s"
                    line_count = max(
                        line_count, math.ceil(len(cell.value) / max(8, widths[cell.column - 1] - 3))
                    )
                cell.font = Font(name="Calibri", size=config.font_size, bold=cell.row == 1)
                cell.alignment = Alignment(
                    vertical="top",
                    wrap_text=True,
                    horizontal="right" if isinstance(cell.value, (int, float)) else "left",
                )
                if cell.row == 1:
                    cell.fill = PatternFill("solid", fgColor="E8EDF2")
                elif headers[cell.column - 1] in {
                    "Доля от всех слов",
                    "Кумулятивное покрытие",
                    "Относительная частота в книге",
                }:
                    cell.number_format = "0.00%"
                elif headers[cell.column - 1] in {"Частота Wordfreq", "Специфичность"}:
                    cell.number_format = "0.000000"
                elif isinstance(cell.value, int):
                    cell.number_format = "#,##0"
            sheet.row_dimensions[row[0].row].height = min(
                409, max(32 if row[0].row == 1 else 30, line_count * 15)
            )
    with atomic_path(target) as tmp:
        book.save(tmp)
    book.close()


def run(paths, output, config, language="es"):
    tables = make_tables({key: read_rows(path) for key, path in paths.items()})
    output.mkdir(parents=True, exist_ok=True)
    if config.xlsx:
        from src.languages import get_profile

        write_excel(output / get_profile(language).export_filename, tables, config)
    if config.csv:
        for (_, headers, rows), name in zip(tables[:2], ("lemmas.csv", "forms.csv")):
            with atomic_path(output / name) as tmp, tmp.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(
                        [
                            "'" + v
                            if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@"))
                            else v
                            for v in row
                        ]
                    )
    logger.info("Экспорт: %s", output)
