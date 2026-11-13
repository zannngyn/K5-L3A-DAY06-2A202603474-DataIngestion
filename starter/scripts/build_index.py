"""Embed strategy A/B chunks and upsert into pgvector; skips chunks whose text is unchanged.

Run from starter/: python scripts/build_index.py
Config C reuses the B index with a metadata filter at query time.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.chunking import STRATEGIES  # noqa: E402
from src.embeddings import OpenRouterEmbedder  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402
from src.store import PgVectorStore, content_hash  # noqa: E402

DEMO_QUESTION = "What ethical concern did Max Weber identify for sociological research?"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv(STARTER / ".env")
    embedder = OpenRouterEmbedder()
    store = PgVectorStore(os.getenv("DATABASE_URL", ""), embedder.dimensions, embedder.model_name)
    store.create_schema()

    pages, _ = load_corpus(ROOT / "data" / "manifest.json")
    run = {"started_at": datetime.now(timezone.utc).isoformat(), "model": embedder.model_name,
           "dimensions": embedder.dimensions, "strategies": {}}
    for name, chunk_fn in STRATEGIES.items():
        chunks = [c for p in pages for c in chunk_fn(p)]
        existing = store.existing_hashes(name)
        todo = [c for c in chunks if existing.get(c.chunk_id) != content_hash(c.text)]
        before = dict(embedder.usage)
        t0 = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in todo]) if todo else []
        t_embed = time.perf_counter() - t0
        result = store.upsert(name, todo, vectors, keep_ids={c.chunk_id for c in chunks})
        run["strategies"][name] = {
            "chunks": len(chunks), "embedded": len(todo), "skipped_unchanged": len(chunks) - len(todo),
            **result, "rows_in_db": store.count(name), "embed_seconds": round(t_embed, 2),
            "prompt_tokens": embedder.usage["prompt_tokens"] - before["prompt_tokens"],
            "cost_credits": round(embedder.usage["cost"] - before["cost"], 8),
        }
        print(name, json.dumps(run["strategies"][name]))

    qvec = embedder.embed_query(DEMO_QUESTION)
    print(f"\nDemo query: {DEMO_QUESTION}")
    for label, strategy, filters in [("A", "A", None), ("B", "B", None), ("C", "B", {"chapter": 2})]:
        print(f"-- {label} filters={filters}")
        for hit in store.search(strategy, qvec, top_k=3, filters=filters):
            print(f"   {hit['score']:.4f} {hit['chunk_id']} ch{hit['chapter']} s{hit['section']} | "
                  f"{hit['text'][:80]!r}")

    run["total_usage"] = embedder.usage
    out = STARTER / "results" / "index_runs.jsonl"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(run) + "\n")
    print(f"\nrun log appended to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
