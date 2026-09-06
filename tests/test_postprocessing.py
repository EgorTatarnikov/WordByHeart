from src.postprocessing.processor import process


def test_postprocess_keeps_clitic_verbs_under_base_infinitive():
    lemmas = [
        {"id": "dar", "lemma": "dar", "pos": "VERB", "count": 2, "observed_forms": {"dar": 2}},
        {"id": "clitic", "lemma": "dar él", "pos": "VERB", "count": 3, "observed_forms": {"darse": 3}},
        {"id": "number", "lemma": "2000", "pos": "NUM", "count": 1, "observed_forms": {"2000": 1}},
    ]
    forms = [
        {
            "id": "dar-form",
            "form": "dar",
            "lemma": "dar",
            "pos": "VERB",
            "count": 2,
            "reference_frequency": 0.001,
        },
        {
            "id": "clitic-form",
            "form": "darse",
            "lemma": "dar él",
            "pos": "VERB",
            "count": 3,
            "reference_frequency": 0.0001,
        },
    ]
    clean_lemmas, clean_forms = process(lemmas, forms)
    assert [(row["lemma"], row["count"]) for row in clean_lemmas] == [("dar", 5)]
    assert clean_lemmas[0]["observed_forms"] == {"dar": 2, "darse": 3}
    assert {row["lemma"] for row in clean_forms} == {"dar"}
