"""Frequency groups share a lemma, while POS entries retain their own identities."""

from collections import defaultdict


def group_lemmas(lemmas, forms):
    by_lemma = defaultdict(list)
    references = defaultdict(dict)
    measured = set()
    for row in lemmas:
        by_lemma[row["lemma"]].append(row)
    for row in forms:
        references[row["lemma"]][row["form"]] = row.get("reference_frequency", 0.0)
        if "reference_frequency" in row:
            measured.add(row["lemma"])
    total = sum(row["count"] for row in lemmas)
    groups = []
    for lemma, rows in by_lemma.items():
        count = sum(row["count"] for row in rows)
        reference = sum(references[lemma].values())
        share = count / total if total else 0.0
        groups.append(
            {
                "lemma": lemma,
                "rows": sorted(rows, key=lambda r: (-r["count"], r["pos"])),
                "count": count,
                "share": share,
                "reference_frequency": reference,
                "specificity": share / max(reference, 1e-12) if reference else 0.0,
            }
        )
        # A measured zero is meaningful; absent reference data is not.
        if lemma in measured:
            groups[-1]["specificity"] = share / max(reference, 1e-12)
    groups.sort(key=lambda g: (-g["count"], g["lemma"]))
    cumulative = 0
    for rank, group in enumerate(groups, 1):
        cumulative += group["count"]
        group.update(rank=rank, cumulative_coverage=cumulative / total if total else 0.0)
    return groups
