"""Atomic artifacts; nested columns use explicit canonical JSON in Parquet."""

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

JSON_FIELDS = {"observed_forms", "contexts", "morph_variants", "original_forms", "review"}


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


@contextmanager
def atomic_path(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid4().hex}.tmp{path.suffix}")
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, value):
    with atomic_path(path) as tmp:
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_rows(path: Path, rows, columns=None):
    records = []
    for row in rows:
        row = asdict(row) if is_dataclass(row) else dict(row)
        records.append({k: canonical(v) if k in JSON_FIELDS else v for k, v in row.items()})
    table = (
        pa.Table.from_pylist(records)
        if records
        else pa.table({k: pa.array([], type=pa.string()) for k in (columns or ["id"])})
    )
    with atomic_path(path) as tmp:
        pq.write_table(table, tmp, compression="zstd")


def iter_rows(path: Path):
    for batch in pq.ParquetFile(path).iter_batches(batch_size=8192):
        for row in batch.to_pylist():
            yield {k: json.loads(v) if k in JSON_FIELDS and v is not None else v for k, v in row.items()}


def read_rows(path: Path) -> list[dict]:
    return list(iter_rows(path))
