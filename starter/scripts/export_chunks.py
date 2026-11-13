"""Export strategy A/B chunks and an ingestion log; check benchmark evidence against chunks.

Run from starter/: python scripts/export_chunks.py
"""
import json
import re
import statistics
import sys
from dataclasses import asdict
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.chunking import STRATEGIES  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def length_stats(chunks) -> dict:
    lengths = [len(c.text) for c in chunks]
    return {"count": len(lengths), "min": min(lengths), "max": max(lengths),
            "mean": round(statistics.mean(lengths), 1), "median": statistics.median(lengths)}


def main() -> None:
    pages, log = load_corpus(ROOT / "data" / "manifest.json")
    out = STARTER / "results"
    out.mkdir(exist_ok=True)

    chunks_by = {}
    for name, fn in STRATEGIES.items():
        chunks = [c for p in pages for c in fn(p)]
        chunks_by[name] = chunks
        with open(out / f"chunks_{name}.jsonl", "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        log[f"strategy_{name}"] = length_stats(chunks)

    page_text = {p.page: norm(p.text) for p in pages}
    questions = json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))["questions"]
    checks = []
    for q in questions:
        quote = norm(q["evidence_quote"])
        row = {"id": q["id"], "in_normalized_page": any(quote in page_text.get(g, "") for g in q["gold_page"])}
        for name, chunks in chunks_by.items():
            row[f"single_chunk_{name}"] = any(c.page in q["gold_page"] and quote in norm(c.text) for c in chunks)
        checks.append(row)
    log["evidence_check"] = checks
    log["evidence_summary"] = {k: sum(r[k] for r in checks) for k in checks[0] if k != "id"}

    (out / "ingestion_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: log[k] for k in ("page_count", "content_pages", "total_chars", "empty_pages",
                                          "error_pages", "strategy_A", "strategy_B", "evidence_summary")},
                     indent=2))
    missing = [r for r in checks if not all(v for k, v in r.items() if k != "id")]
    for r in missing:
        print("not fully contained:", r)


if __name__ == "__main__":
    main()
