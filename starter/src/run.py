"""Day 06 retrieval benchmark: run configs A/B/C on one split, save traces, metrics and audit sheets.

Run from starter/ after scripts/build_index.py:
    python -m src.run                              # dev split (default)
    python -m src.run --split test --confirm-test  # only after the config is chosen on dev
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import STRATEGIES
from .embeddings import QUERY_INSTRUCTION, OpenRouterEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_corpus
from .store import PgVectorStore, content_hash

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
RESULTS = STARTER / "results"
TOP_K = 3
# config -> (index strategy, use question filter)
CONFIGS = {"A": ("A", False), "B": ("B", False), "C": ("B", True)}
COHERENCE_PAGES = [19, 23, 27, 31, 35, 49, 53, 57, 61, 65]
REQUIRED_FIELDS = ["id", "split", "question", "expected_answer", "gold_source_id", "gold_page", "evidence_quote"]


class BenchmarkInvalid(ValueError):
    pass


def validate_benchmark(questions: list[dict[str, Any]]) -> None:
    problems = []
    for q in questions:
        missing = [f for f in REQUIRED_FIELDS if q.get(f) in (None, "", [])]
        if missing:
            problems.append(f"{q.get('id')}: missing {missing}")
        if q.get("split") not in ("dev", "test"):
            problems.append(f"{q.get('id')}: split must be dev/test")
        if not isinstance(q.get("gold_page"), list):
            problems.append(f"{q.get('id')}: gold_page must be a list")
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        problems.append("duplicate question ids")
    dev = sum(q.get("split") == "dev" for q in questions)
    test = sum(q.get("split") == "test" for q in questions)
    filtered = [q for q in questions if q.get("filter")]
    if len(questions) < 20 or dev < 15 or test < 5:
        problems.append(f"need >=20 questions, >=15 dev, >=5 test; got {len(questions)}/{dev}/{test}")
    if len(filtered) < 3 or not any(q["split"] == "test" for q in filtered):
        problems.append("need >=3 filter questions including >=1 test")
    if problems:
        raise BenchmarkInvalid("; ".join(problems))


def check_index_fresh(store: PgVectorStore, pages) -> dict[str, int]:
    counts = {}
    for name, chunk_fn in STRATEGIES.items():
        expected = {c.chunk_id: content_hash(c.text) for p in pages for c in chunk_fn(p)}
        if store.existing_hashes(name) != expected:
            raise RuntimeError(f"index '{name}' is stale or missing; run: python scripts/build_index.py")
        counts[name] = len(expected)
    return counts


def git_state() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain"))}


def write_csv_once(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    """Never overwrite an audit sheet that may already contain manual labels."""
    if path.exists():
        print(f"keep existing {path.relative_to(ROOT)} (delete it to regenerate)")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)}")


def coherence_sheet(pages) -> None:
    by_page = {p.page: p for p in pages}
    rows = []
    for i, number in enumerate(COHERENCE_PAGES, start=1):
        page = by_page[number]
        offset = len(page.text) // 2
        for name, chunk_fn in STRATEGIES.items():
            chunk = next(c for c in chunk_fn(page)
                         if c.metadata["char_start"] <= offset < c.metadata["char_end"])
            rows.append([f"pos{i:02d}", number, offset, name, chunk.chunk_id, len(chunk.text), chunk.text, "", ""])
    write_csv_once(RESULTS / "audit_coherence.csv",
                   ["position_id", "page", "char_offset", "strategy", "chunk_id", "chunk_chars", "text",
                    "coherence_0_2", "reason"], rows)


def test_sheets(traces: list[dict[str, Any]]) -> None:
    meta_rows, ground_rows = [], []
    for t in traces:
        required = (t["filter"] or {}).get("chapter", "")
        for r in t["top_k"]:
            meta_rows.append([t["id"], t["config"], r["rank"], r["chunk_id"], r["source"], r["page"],
                              r["chapter"], r["section"], required, r["text"][:300], "", "", "", "", ""])
        flat = [v for r in t["top_k"] for v in (r["chunk_id"], r["page"], r["text"])]
        ground_rows.append([t["id"], t["config"], t["question"], t["expected_answer"], *flat,
                            t["hit@3"], "", ""])
    write_csv_once(RESULTS / "audit_metadata.csv",
                   ["question_id", "config", "rank", "chunk_id", "source", "page", "chapter", "section",
                    "required_chapter", "text_excerpt", "source_ok", "page_ok", "chapter_ok", "section_ok", "notes"],
                   meta_rows)
    header = ["question_id", "config", "question", "expected_answer"]
    for k in range(1, TOP_K + 1):
        header += [f"top{k}_chunk_id", f"top{k}_page", f"top{k}_text"]
    write_csv_once(RESULTS / "audit_grounding.csv", header + ["auto_hit@3", "grounding_0_2", "reason"],
                   ground_rows)


def summary_markdown(summary: dict[str, Any], chunk_counts: dict[str, int]) -> str:
    fmt = lambda r: "N/A" if r == "N/A" else f"{r['n']}/{r['N']} ({r['pct']}%)"  # noqa: E731
    lines = ["| Config | Split | Hit@1 | Evidence Hit@3 | Filter compliance | Chunks | Failures |",
             "|---|---|---|---|---|---|---|"]
    for s in summary.values():
        chunks = chunk_counts[CONFIGS[s["config"]][0]]
        failures = ", ".join(f"{k}={v}" for k, v in s["failures"].items()) or "-"
        lines.append(f"| {s['config']} | {s['split']} | {fmt(s['hit@1'])} | {fmt(s['hit@3'])} | "
                     f"{fmt(s['filter_compliance'])} | {chunks} | {failures} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--confirm-test", action="store_true",
                        help="required for --split test: the config was already chosen on dev")
    args = parser.parse_args(argv)
    if args.split == "test" and not args.confirm_test:
        sys.exit("Refusing to run test: choose the config on dev first, then pass --confirm-test.")

    load_dotenv(STARTER / ".env")
    benchmark = json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))
    questions = benchmark["questions"]
    validate_benchmark(questions)
    pages, _ = load_corpus(ROOT / "data" / "manifest.json")
    content_pages = sum(1 for p in pages if p.text)
    if content_pages < 30:
        raise BenchmarkInvalid(f"corpus has {content_pages} content pages, need >=30")

    embedder = OpenRouterEmbedder()
    store = PgVectorStore(os.getenv("DATABASE_URL", ""), embedder.dimensions, embedder.model_name)
    chunk_counts = check_index_fresh(store, pages)
    RESULTS.mkdir(exist_ok=True)

    selected = [q for q in questions if q["split"] == args.split]
    t0 = time.perf_counter()
    qvecs = {q["id"]: embedder.embed_query(q["question"]) for q in selected}
    embed_seconds = time.perf_counter() - t0

    traces, latency = [], {}
    for config, (strategy, use_filter) in CONFIGS.items():
        t_config = time.perf_counter()
        for q in selected:
            filters = q.get("filter") if use_filter else None
            hits = store.search(strategy, qvecs[q["id"]], top_k=TOP_K, filters=filters)
            trace = evaluate_query({**q, "filter_applied": filters}, hits)
            trace.update({"config": config, "index": strategy})
            traces.append(trace)
        latency[config] = round((time.perf_counter() - t_config) / len(selected) * 1000, 1)

    summary = summarize(traces)
    with open(RESULTS / f"traces_{args.split}.jsonl", "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    (RESULTS / f"summary_{args.split}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = summary_markdown(summary, chunk_counts)
    (RESULTS / f"summary_{args.split}.md").write_text(md, encoding="utf-8")
    meta = {
        "ran_at": datetime.now(timezone.utc).isoformat(), "split": args.split, "questions": len(selected),
        "top_k": TOP_K, "configs": {k: {"index": v[0], "filter": v[1]} for k, v in CONFIGS.items()},
        "model": embedder.model_name, "dimensions": embedder.dimensions,
        "query_instruction": QUERY_INSTRUCTION, "chunk_counts": chunk_counts,
        "query_embed_seconds": round(embed_seconds, 2), "query_embed_usage": embedder.usage,
        "search_ms_per_query": latency, "git": git_state(),
        "dev_summary_existed_before": (RESULTS / "summary_dev.json").exists() if args.split == "test" else None,
    }
    (RESULTS / f"run_meta_{args.split}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    coherence_sheet(pages)
    if args.split == "test":
        test_sheets(traces)
    print(md)
    print(f"traces: {len(traces)} -> {(RESULTS / f'traces_{args.split}.jsonl').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
