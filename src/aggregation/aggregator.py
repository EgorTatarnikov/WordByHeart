import logging
from collections import Counter
from dataclasses import asdict

from src.models import FormEntry, LemmaEntry
from src.nlp.token_filter import include
from src.storage import digest, iter_rows, write_rows

logger = logging.getLogger(__name__)


def entry_id(kind, *key):
    return kind + ":" + digest(key)


def aggregate(occurrences, config, filters):
    lemmas, forms = {}, {}
    for row in occurrences:
        if not include(row, filters):
            continue
        lemma, pos, form = row["lemma"].casefold(), row["pos"], row["normalized_form"].casefold()
        lk, fk = (lemma, pos), (form, lemma, pos)
        if lk not in lemmas:
            lemmas[lk] = {"forms": Counter(), "contexts": [], "morph": set(), "chunks": set()}
        if fk not in forms:
            forms[fk] = {"count": 0, "contexts": [], "morph": set(), "original": set()}
        le, fe = lemmas[lk], forms[fk]
        le["forms"][form] += 1
        le["chunks"].add(row["chunk_id"])
        fe["count"] += 1
        fe["original"].add(row["original_text"])
        for entry in (le, fe):
            entry["morph"].add(row["morph"])
            context = row["context"]
            if context and context not in entry["contexts"]:
                entry["contexts"].append(context)
                entry["contexts"].sort(key=lambda c: (abs(len(c) - 100), c))
                del entry["contexts"][config.max_contexts :]
    lemma_rows = [
        asdict(
            LemmaEntry(
                entry_id("lemma", *key),
                *key,
                sum(v["forms"].values()),
                dict(sorted(v["forms"].items(), key=lambda x: (-x[1], x[0]))),
                v["contexts"],
                sorted(v["morph"]),
                len(v["chunks"]),
            )
        )
        for key, v in lemmas.items()
    ]
    form_rows = [
        asdict(
            FormEntry(
                entry_id("form", *key),
                *key,
                v["count"],
                sorted(v["morph"]),
                v["contexts"],
                sorted(v["original"]),
            )
        )
        for key, v in forms.items()
    ]
    lemma_rows.sort(key=lambda r: (-r["count"], r["lemma"], r["pos"]))
    form_rows.sort(key=lambda r: (-r["count"], r["form"], r["lemma"], r["pos"]))
    total = sum(r["count"] for r in lemma_rows)
    cumulative = 0
    for rank, row in enumerate(lemma_rows, 1):
        cumulative += row["count"]
        row.update(rank=rank, share=row["count"] / total, cumulative_coverage=cumulative / total)
    for rank, row in enumerate(form_rows, 1):
        row["rank"] = rank
    return lemma_rows, form_rows


def run(source, lemma_target, form_target, config, filters):
    lemmas, forms = aggregate(iter_rows(source), config, filters)
    write_rows(lemma_target, lemmas)
    write_rows(form_target, forms)
    logger.info("Уникальных lemma+POS: %d; form+lemma+POS: %d", len(lemmas), len(forms))
