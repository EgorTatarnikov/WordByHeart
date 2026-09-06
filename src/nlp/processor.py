import logging
from dataclasses import asdict

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from src.models import Occurrence
from src.preprocessing.chunker import chunks
from src.storage import atomic_path

logger = logging.getLogger(__name__)

SCHEMA = pa.schema(
    [
        (
            k,
            pa.bool_()
            if k.startswith("is_")
            else pa.int64()
            if k.endswith("_id") or k == "token_index"
            else pa.string(),
        )
        for k in Occurrence.__dataclass_fields__
    ]
)


def run(source, target, config):
    import spacy

    try:
        nlp = spacy.load(config.model)
    except OSError as exc:
        raise RuntimeError(f"Установите модель: python -m spacy download {config.model}") from exc
    text = source.read_text(encoding="utf-8")
    nlp.max_length = max(nlp.max_length, len(text) + 1)
    count = words = chunk_count = sentence_id = 0
    stream = ((chunk.text, chunk) for chunk in chunks(text, config.chunk_size))
    with atomic_path(target) as tmp, pq.ParquetWriter(tmp, SCHEMA, compression="zstd") as writer:
        for doc, chunk in tqdm(
            nlp.pipe(stream, as_tuples=True, batch_size=config.batch_size), desc="NLP", unit="chunk"
        ):
            chunk_count += 1
            if chunk.split_sentence:
                logger.warning("Chunk %d: очень длинное предложение разделено по пробелу", chunk.chunk_id)
            rows = []
            for sentence in doc.sents:
                context = sentence.text.strip()
                for token in sentence:
                    if token.is_punct or token.is_space:
                        count += 1
                        continue
                    words += 1
                    rows.append(
                        asdict(
                            Occurrence(
                                token.text,
                                token.text.casefold(),
                                token.lemma_.casefold(),
                                token.pos_,
                                str(token.morph),
                                token.is_alpha,
                                token.is_punct,
                                token.is_space,
                                context,
                                chunk.chunk_id,
                                chunk.paragraph_id,
                                sentence_id,
                                count,
                            )
                        )
                    )
                    count += 1
                sentence_id += 1
            if rows:
                writer.write_table(pa.Table.from_pylist(rows, schema=SCHEMA))
    logger.info("Chunks: %d; токенов: %d; слов: %d", chunk_count, count, words)
