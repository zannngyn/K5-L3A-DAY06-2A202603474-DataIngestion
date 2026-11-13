"""Store and search vectors using PostgreSQL + pgvector (exact cosine search, no ANN index)."""
import hashlib
import json
import math
from typing import Any

import psycopg

from .models import Chunk

# Only these metadata fields may be used as filters; values are always SQL parameters.
FILTER_COLUMNS = {"chapter": "chapter", "section": "section", "document_id": "document_id"}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int, model_name: str) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is not set")
        if not 0 < dimensions <= 16000:
            raise ValueError(f"pgvector supports 1..16000 dims, got {dimensions}")
        self.database_url = database_url
        self.dimensions = dimensions
        self.model_name = model_name

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, connect_timeout=5)

    def create_schema(self) -> None:
        # Exact search only: HNSW/IVFFlat on `vector` cap at 2000 dims (pgvector docs).
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy     text    NOT NULL,
                    chunk_id     text    NOT NULL,
                    document_id  text    NOT NULL,
                    source       text    NOT NULL,
                    page         integer NOT NULL,
                    chapter      integer,
                    section      text,
                    text         text    NOT NULL,
                    metadata     jsonb   NOT NULL,
                    content_hash text    NOT NULL,
                    model        text    NOT NULL,
                    embedding    vector({self.dimensions}) NOT NULL,
                    updated_at   timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (strategy, chunk_id)
                )""")
            row = conn.execute(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'").fetchone()
            if row[0] != f"vector({self.dimensions})":
                raise RuntimeError(f"existing chunks.embedding is {row[0]}, expected vector({self.dimensions})")

    def existing_hashes(self, strategy: str) -> dict[str, str]:
        """chunk_id -> content_hash for rows embedded with the current model."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT chunk_id, content_hash FROM chunks WHERE strategy = %s AND model = %s",
                (strategy, self.model_name)).fetchall()
        return dict(rows)

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]],
               keep_ids: set[str] | None = None) -> dict[str, int]:
        """Insert/update `chunks`, then delete rows of this strategy not in `keep_ids`.

        Each run indexes the full corpus for a strategy. `keep_ids` is the full current chunk ID
        set (defaults to the IDs being written), so unchanged chunks skipped for re-embedding stay.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        for chunk, vec in zip(chunks, vectors):
            if len(vec) != self.dimensions or not all(math.isfinite(x) for x in vec):
                raise ValueError(f"bad vector for {chunk.chunk_id}")
        keep = set(keep_ids) if keep_ids is not None else {c.chunk_id for c in chunks}
        if not keep:
            raise ValueError("refusing to upsert with an empty keep set (would delete the whole strategy)")
        with self._connect() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO chunks (strategy, chunk_id, document_id, source, page, chapter, section,
                                        text, metadata, content_hash, model, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id, source = EXCLUDED.source,
                        page = EXCLUDED.page, chapter = EXCLUDED.chapter, section = EXCLUDED.section,
                        text = EXCLUDED.text, metadata = EXCLUDED.metadata,
                        content_hash = EXCLUDED.content_hash, model = EXCLUDED.model,
                        embedding = EXCLUDED.embedding, updated_at = now()
                """, [(strategy, c.chunk_id, c.document_id, c.source, c.page, c.metadata.get("chapter"),
                       c.metadata.get("section"), c.text, json.dumps(c.metadata, ensure_ascii=False),
                       content_hash(c.text), self.model_name, _vector_literal(v))
                      for c, v in zip(chunks, vectors)])
                cur.execute(
                    "DELETE FROM chunks WHERE strategy = %s AND NOT chunk_id = ANY(%s)",
                    (strategy, sorted(keep)))
                deleted = cur.rowcount
        return {"written": len(chunks), "deleted_obsolete": deleted}

    def count(self, strategy: str) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,)).fetchone()[0]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Exact cosine ranking; score = 1 - cosine distance. Unknown filter keys raise."""
        if len(query_vector) != self.dimensions:
            raise ValueError(f"query vector has {len(query_vector)} dims, expected {self.dimensions}")
        where = ["strategy = %s", "model = %s"]
        params: list[Any] = [strategy, self.model_name]
        for key, value in (filters or {}).items():
            if key not in FILTER_COLUMNS:
                raise ValueError(f"filter '{key}' not allowed; allowed: {sorted(FILTER_COLUMNS)}")
            where.append(f"{FILTER_COLUMNS[key]} = %s")
            params.append(value)
        qvec = _vector_literal(query_vector)
        sql = f"""
            SELECT chunk_id, document_id, source, page, chapter, section, text, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM chunks WHERE {' AND '.join(where)}
            ORDER BY embedding <=> %s::vector, chunk_id
            LIMIT %s"""
        with self._connect() as conn:
            rows = conn.execute(sql, [qvec, *params, qvec, top_k]).fetchall()
        cols = ["chunk_id", "document_id", "source", "page", "chapter", "section", "text", "metadata", "score"]
        return [dict(zip(cols, r)) for r in rows]
