from src.cards.formatter import card_content
from src.config import Export
from src.export.excel_exporter import KAIKKI_TRANSLATION_CREDIT, write_excel
from src.pronunciation.cyrillic import formatted_cyrillic


def list_filename(language):
    return {"en": "english_list.xlsx", "es": "spanish_list.xlsx"}[language]


def render_learning_list(cards, target, cards_config, language="es", machine_translation=False):
    rows = []
    for card in cards:
        front, ipa, translations, forms = card_content(card, cards_config.max_forms, language)
        row = [front, ipa]
        if language == "es":
            row.append(formatted_cyrillic(card.ipa))
        rows.append([*row, "\n".join(translations), forms])
    headers = ["Слово", "Транскрипция"]
    if language == "es":
        headers.append("Транскрипция Кириллица")
    write_excel(
        target,
        [("Список для изучения", [*headers, "Перевод", "Словоформы"], rows)],
        Export(),
        description=None if machine_translation else KAIKKI_TRANSLATION_CREDIT,
    )
