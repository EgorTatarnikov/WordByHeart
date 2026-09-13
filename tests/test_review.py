from src.export.review import make_review_rows


def test_normal_homonymy_does_not_require_user_attention():
    data = {
        "lemmas": [],
        "forms": [],
        "validation": [
            {"id": "x", "category": "ambiguity", "severity": "info", "message": "watch: lemma/POS"}
        ],
    }
    assert make_review_rows(data)[0][2] == "Замечаний нет"
    data["validation"] = []
    assert make_review_rows(data)[0][2] == "Замечаний нет"


def test_review_localizes_prioritizes_and_deduplicates():
    data = {
        "lemmas": [{"id": "lemma", "lemma": "watch", "pos": "VERB"}],
        "forms": [{"id": "form", "lemma": "watch", "form": "watch", "pos": "VERB"}],
        "validation": [
            {"id": "lemma", "category": "ipa", "severity": "review", "message": "unsupported input"},
            {"id": "form", "category": "ipa", "severity": "review", "message": "unsupported input"},
            {"id": "lemma", "category": "translation", "severity": "error", "message": "Пустой ru"},
        ],
    }
    rows = make_review_rows(data)
    assert len(rows) == 2
    assert rows[0][:3] == ["watch", "глагол", "Ошибка"]
    assert rows[0][3] == "Отсутствует перевод на русский"
    assert rows[1][3] == "Не удалось получить транскрипцию"
    assert all(row[4] for row in rows)


def test_integrity_errors_remain_visible_without_technical_ids():
    rows = make_review_rows(
        {
            "lemmas": [],
            "forms": [],
            "validation": [
                {
                    "id": "internal-hash",
                    "category": "grammar",
                    "severity": "error",
                    "message": "Неизвестный ID",
                }
            ],
        }
    )
    assert rows[0][0] == "Весь словарь"
    assert rows[0][2] == "Ошибка"
    assert "разработчику" in rows[0][4]
    assert "internal-hash" not in str(rows)
