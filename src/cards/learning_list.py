from src.cards.formatter import card_content
from src.config import Export
from src.export.excel_exporter import write_excel


def list_filename(language):
    return {"en": "english_list.xlsx", "es": "spanish_list.xlsx"}[language]


def render_learning_list(cards, target, cards_config, language="es"):
    rows = []
    for card in cards:
        front, ipa, translations, forms = card_content(card, cards_config.max_forms, language)
        rows.append([front, ipa, "\n".join(translations), forms])
    write_excel(
        target,
        [("Список для изучения", ["Слово", "Транскрипция", "Перевод", "Словоформы"], rows)],
        Export(),
    )
