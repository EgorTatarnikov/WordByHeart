import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

from src.config import TranslationSettings
from src.export.excel_exporter import make_tables
from src.pronunciation.cache import cache_key as ipa_key
from src.storage import read_rows, write_rows
from src.translation.cache import cache_key
from src.translation.openai_translator import OpenAITranslator, parse_response, run, translate_entries
from src.translation.selection import select_lemmas_by_cumulative_coverage


def entry(id="one"):
    return {
        "id": id,
        "kind": "form",
        "form": "vino",
        "lemma": "venir",
        "pos": "VERB",
        "morph_variants": ["Tense=Past"],
        "contexts": ["Juan vino a casa."],
    }


def test_cache_keys_include_context_pos_morph_model_prompt():
    config = TranslationSettings(model="test-model")
    row = entry()
    original = cache_key(row, config)
    for key, value in [
        ("lemma", "vino"),
        ("pos", "NOUN"),
        ("contexts", ["El vino era bueno."]),
        ("morph_variants", ["Tense=Pres"]),
        ("form", "viene"),
    ]:
        assert cache_key({**row, key: value}, config) != original
    for key, value in [("model", "other"), ("provider", "other"), ("prompt_version", "2")]:
        assert cache_key(row, config.model_copy(update={key: value})) != original
    assert ipa_key("casa", "es", "1") != ipa_key("casa", "es-419", "1")
    assert ipa_key("casa", "es", "1") != ipa_key("casa", "es", "2")
    assert cache_key(row, config) == cache_key(
        row, config.model_copy(update={"cumulative_coverage_limit": 90})
    )


def coverage_rows():
    lemmas = [
        {
            "id": "lemma-a",
            "lemma": "a",
            "pos": "NOUN",
            "count": 50,
            "cumulative_coverage": 0.5,
            "observed_forms": {"a": 50},
            "morph_variants": [],
            "contexts": ["a"],
        },
        {
            "id": "lemma-b",
            "lemma": "b",
            "pos": "VERB",
            "count": 30,
            "cumulative_coverage": 0.8,
            "observed_forms": {"b": 30},
            "morph_variants": [],
            "contexts": ["b"],
        },
        {
            "id": "lemma-c",
            "lemma": "c",
            "pos": "NOUN",
            "count": 10,
            "cumulative_coverage": 0.9,
            "observed_forms": {"c": 10},
            "morph_variants": [],
            "contexts": ["c"],
        },
        {
            "id": "lemma-d",
            "lemma": "d",
            "pos": "NOUN",
            "count": 10,
            "cumulative_coverage": 1.0,
            "observed_forms": {"d": 10},
            "morph_variants": [],
            "contexts": ["d"],
        },
    ]
    forms = [
        {
            "id": f"form-{row['lemma']}",
            "form": row["lemma"],
            "lemma": row["lemma"],
            "pos": row["pos"],
            "morph_variants": [],
            "contexts": [row["lemma"]],
        }
        for row in lemmas
    ]
    return lemmas, forms


def test_selection_default_exact_boundary_and_crossing():
    lemmas, forms = coverage_rows()
    assert select_lemmas_by_cumulative_coverage(lemmas, forms, 100).eligible_lemma_ids == {
        "lemma-a",
        "lemma-b",
        "lemma-c",
        "lemma-d",
    }
    exact = select_lemmas_by_cumulative_coverage(lemmas, forms, 90)
    assert exact.eligible_lemma_ids == {"lemma-a", "lemma-b", "lemma-c"}
    assert exact.eligible_form_ids == {"form-a", "form-b", "form-c"}
    assert exact.actual_coverage == pytest.approx(0.9)
    lemmas[1]["cumulative_coverage"] = 0.898
    lemmas[2]["cumulative_coverage"] = 0.902
    crossing = select_lemmas_by_cumulative_coverage(lemmas, forms, 90)
    assert crossing.eligible_lemma_ids == {"lemma-a", "lemma-b", "lemma-c"}
    assert crossing.actual_coverage == pytest.approx(0.902)


def test_selection_keeps_homonym_pos_separate():
    lemmas = [
        {"id": "noun", "lemma": "vino", "pos": "NOUN", "count": 70, "cumulative_coverage": 0.7},
        {"id": "verb", "lemma": "venir", "pos": "VERB", "count": 20, "cumulative_coverage": 0.9},
    ]
    forms = [
        {"id": "noun-form", "form": "vino", "lemma": "vino", "pos": "NOUN"},
        {"id": "verb-form", "form": "vino", "lemma": "venir", "pos": "VERB"},
    ]
    selection = select_lemmas_by_cumulative_coverage(lemmas, forms, 70)
    assert selection.eligible_lemma_ids == {"noun"}
    assert selection.eligible_form_ids == {"noun-form"}


@pytest.mark.parametrize("value", [100, 90, 90.5])
def test_coverage_limit_config_valid(value):
    assert TranslationSettings(cumulative_coverage_limit=value).cumulative_coverage_limit == value


@pytest.mark.parametrize("value", [0, -10, 100.01])
def test_coverage_limit_config_invalid(value):
    with pytest.raises(ValueError, match="cumulative_coverage_limit must be > 0 and <= 100"):
        TranslationSettings(cumulative_coverage_limit=value)


def test_coverage_expansion_reuses_cache_and_artifact_keeps_all_entries(tmp_path):
    lemmas, forms = coverage_rows()
    lemma_path, form_path = tmp_path / "lemmas.parquet", tmp_path / "forms.parquet"
    target, cache = tmp_path / "translations.parquet", tmp_path / "translations.sqlite"
    write_rows(lemma_path, lemmas)
    write_rows(form_path, forms)
    calls = []

    class Provider:
        def translate(self, rows):
            calls.append([row["id"] for row in rows])
            return [{"id": row["id"], "ru": "перевод", "en": "translation"} for row in rows]

    config = TranslationSettings(model="test", batch_size=20, cumulative_coverage_limit=80)
    run(lemma_path, form_path, target, cache, config, Provider())
    assert calls == [["lemma-a", "lemma-b", "form-a", "form-b"]]
    first = {row["id"]: row for row in read_rows(target)}
    assert len(first) == 8
    assert first["lemma-c"]["translation_eligible"] is False
    assert first["lemma-c"]["ru"] == ""
    calls.clear()
    config.cumulative_coverage_limit = 90
    run(lemma_path, form_path, target, cache, config, Provider())
    assert calls == [["lemma-c", "form-c"]]
    second = {row["id"]: row for row in read_rows(target)}
    assert second["lemma-d"]["translation_eligible"] is False
    assert second["lemma-d"]["ru"] == ""


def test_coverage_reduction_does_not_delete_cache_or_send_api_requests(tmp_path):
    lemmas, forms = coverage_rows()
    lemma_path, form_path = tmp_path / "lemmas.parquet", tmp_path / "forms.parquet"
    target, cache = tmp_path / "translations.parquet", tmp_path / "translations.sqlite"
    write_rows(lemma_path, lemmas)
    write_rows(form_path, forms)

    class Provider:
        def __init__(self):
            self.calls = []

        def translate(self, rows):
            self.calls.append([row["id"] for row in rows])
            return [{"id": row["id"], "ru": "перевод", "en": "translation"} for row in rows]

    first_provider = Provider()
    run(
        lemma_path,
        form_path,
        target,
        cache,
        TranslationSettings(model="test", cumulative_coverage_limit=100),
        first_provider,
    )
    assert first_provider.calls == [
        ["lemma-a", "lemma-b", "lemma-c", "lemma-d", "form-a", "form-b", "form-c", "form-d"]
    ]
    reduced_provider = Provider()
    run(
        lemma_path,
        form_path,
        target,
        cache,
        TranslationSettings(model="test", cumulative_coverage_limit=90),
        reduced_provider,
    )
    assert reduced_provider.calls == []
    rows = {row["id"]: row for row in read_rows(target)}
    assert rows["lemma-d"]["translation_eligible"] is False
    assert rows["lemma-d"]["ru"] == ""


def test_export_tables_keep_entries_outside_translation_coverage(tmp_path):
    lemmas, forms = coverage_rows()
    lemma_path, form_path = tmp_path / "lemmas.parquet", tmp_path / "forms.parquet"
    target, cache = tmp_path / "translations.parquet", tmp_path / "translations.sqlite"
    write_rows(lemma_path, lemmas)
    write_rows(form_path, forms)

    class Provider:
        def translate(self, rows):
            return [{"id": row["id"], "ru": "перевод", "en": "translation"} for row in rows]

    run(
        lemma_path,
        form_path,
        target,
        cache,
        TranslationSettings(model="test", cumulative_coverage_limit=90),
        Provider(),
    )
    translations = read_rows(target)
    for rank, row in enumerate(lemmas, 1):
        row.update(rank=rank, share=row["count"] / 100, chunk_count=1)
    for rank, row in enumerate(forms, 1):
        row.update(rank=rank, count=1)
    grammar = [
        {
            "id": row["id"],
            "learning_form": "",
            "grammatical_gender": "",
            "grammar_forms": "",
            "infinitive": "",
            "conjugation_group": "",
            "regularity": "",
            "morph_description": "",
        }
        for row in lemmas + forms
    ]
    ipa = [{"text": text, "ipa": "ipa"} for text in {r["lemma"] for r in lemmas} | {r["form"] for r in forms}]
    tables = make_tables(
        {
            "lemmas": lemmas,
            "forms": forms,
            "lemma_grammar": grammar[: len(lemmas)],
            "form_grammar": grammar[len(lemmas) :],
            "ipa": ipa,
            "translations": translations,
            "validation": [],
        }
    )
    assert len(tables[0][2]) == len(lemmas)
    assert len(tables[1][2]) == len(forms)
    rare_lemma_row = next(row for row in tables[0][2] if row[1] == "d")
    assert rare_lemma_row[14:16] == ["", ""]


@pytest.mark.parametrize(
    "raw",
    [
        "{}",
        "not json",
        '{"entries":[{"id":"x","ru":"дом","en":"house"}]}',
        '{"entries":[{"id":"one","ru":"","en":"house"}]}',
        '{"entries":[{"id":"one","ru":7,"en":"house"}]}',
        '{"entries":[{"id":"one","ru":"дом","en":"house"},{"id":"one","ru":"дом","en":"house"}]}',
    ],
)
def test_bad_json_schema_and_ids(raw):
    with pytest.raises(ValueError):
        parse_response(raw, {"one"})


def test_partial_retry_and_cache_resume(tmp_path, monkeypatch):
    monkeypatch.setattr("src.translation.openai_translator.time.sleep", lambda _: None)
    calls = []

    class Provider:
        def translate(self, rows):
            calls.append([r["id"] for r in rows])
            return [{"id": rows[0]["id"], "ru": "пришёл", "en": "came"}]

    config = TranslationSettings(model="test", batch_size=2)
    rows = [entry("one"), entry("two")]
    path = tmp_path / "cache.sqlite"
    result = translate_entries(rows, config, path, Provider())
    assert len(result) == 2
    assert calls == [["one", "two"], ["two"]]
    calls.clear()
    assert translate_entries(rows, config, path, Provider()) == result
    assert calls == []


@pytest.mark.parametrize("error_kind", ["invalid", "network", "rate_limit"])
def test_bounded_retries(tmp_path, monkeypatch, error_kind):
    monkeypatch.setattr("src.translation.openai_translator.time.sleep", lambda _: None)
    calls = []

    class Provider:
        def translate(self, rows):
            calls.append(rows)
            if error_kind == "network":
                raise APIConnectionError(request=httpx.Request("POST", "https://example.org"))
            if error_kind == "rate_limit":
                raise RateLimitError(
                    "limit",
                    response=httpx.Response(429, request=httpx.Request("POST", "https://example.org")),
                    body=None,
                )
            return [{"id": "unexpected", "ru": "дом", "en": "house"}]

    config = TranslationSettings(model="test", max_attempts=2)
    with pytest.raises(RuntimeError, match="не завершён"):
        translate_entries([entry()], config, tmp_path / "cache.sqlite", Provider())
    assert len(calls) == 2


def test_successful_batch_survives_later_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("src.translation.openai_translator.time.sleep", lambda _: None)
    config = TranslationSettings(model="test", batch_size=1, max_attempts=1)

    class Partial:
        def translate(self, rows):
            if rows[0]["id"] == "two":
                raise ValueError("bad JSON")
            return [{"id": "one", "ru": "пришёл", "en": "came"}]

    rows = [entry("one"), entry("two")]
    path = tmp_path / "cache.sqlite"
    with pytest.raises(RuntimeError):
        translate_entries(rows, config, path, Partial())
    calls = []

    class Resume:
        def translate(self, rows):
            calls.extend(r["id"] for r in rows)
            return [{"id": r["id"], "ru": "пришёл", "en": "came"} for r in rows]

    assert len(translate_entries(rows, config, path, Resume())) == 2
    assert calls == ["two"]


def test_failed_batch_is_retried_in_smaller_batches(tmp_path):
    calls = []

    class Provider:
        def translate(self, rows):
            calls.append([row["id"] for row in rows])
            if len(rows) > 2:
                raise ValueError("batch is too large")
            return [{"id": row["id"], "ru": "перевод", "en": "translation"} for row in rows]

    rows = [entry(str(index)) for index in range(4)]
    result = translate_entries(
        rows,
        TranslationSettings(model="test", batch_size=4, max_attempts=1),
        tmp_path / "cache.sqlite",
        Provider(),
    )
    assert len(result) == 4
    assert calls == [["0", "1", "2", "3"], ["0", "1"], ["2", "3"]]


def test_openai_structured_request_and_refusal():
    calls = []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                status="completed",
                output_text=json.dumps({"entries": [{"id": "one", "ru": "пришёл", "en": "came"}]}),
            )

    client = SimpleNamespace(responses=Responses())
    provider = OpenAITranslator(TranslationSettings(model="configured"), client)
    assert provider.translate([entry()])[0]["en"] == "came"
    assert calls[0]["model"] == "configured"
    assert calls[0]["text"]["format"]["strict"] is True
    assert calls[0]["store"] is False
    client.responses.create = lambda **_: SimpleNamespace(status="completed", output_text="")
    with pytest.raises(ValueError, match="refusal"):
        provider.translate([entry()])
