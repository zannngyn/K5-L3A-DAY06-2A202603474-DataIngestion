"""Evaluate retrieved evidence and preserve per-query traces.

Hit = chunk from a gold source, on a gold page, containing the full evidence quote
(whitespace-normalized). Coherence/grounding are human labels and are never inferred here.
"""
import re
import unicodedata
from collections import defaultdict
from typing import Any

_EDGE = 30  # chars used to detect evidence cut across chunk boundaries


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _gold_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Primary gold plus any documented alternatives ({gold_source_id, gold_page, evidence_quote})."""
    options = [question] + list(question.get("alternative_gold", []))
    return [{"source": o["gold_source_id"], "pages": set(o["gold_page"]), "quote": _norm(o["evidence_quote"])}
            for o in options]


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    gold = _gold_options(question)
    filt = question.get("filter_applied")
    ranked = []
    for rank, hit in enumerate(hits, start=1):
        text = _norm(hit["text"])
        on_page = [g for g in gold if hit["document_id"] == g["source"] and hit["page"] in g["pages"]]
        full = any(g["quote"] in text for g in on_page)
        partial = not full and any(g["quote"][:_EDGE] in text or g["quote"][-_EDGE:] in text for g in on_page)
        ranked.append({
            "rank": rank, "chunk_id": hit["chunk_id"], "document_id": hit["document_id"],
            "source": hit["source"], "page": hit["page"], "chapter": hit["chapter"],
            "section": hit["section"], "score": round(float(hit["score"]), 6),
            "gold_page_match": bool(on_page), "evidence_full": full, "evidence_partial": partial,
            "text": hit["text"],
        })
    first_hit = next((r["rank"] for r in ranked if r["evidence_full"]), None)
    if first_hit is not None:
        failure = None
    elif any(r["evidence_partial"] for r in ranked):
        failure = "partial_evidence"
    elif any(r["gold_page_match"] for r in ranked):
        failure = "gold_page_without_evidence"
    else:
        failure = "wrong_page"
    required = (question.get("filter") or {}).get("chapter")
    return {
        "id": question["id"], "split": question["split"], "type": question.get("type"),
        "question": question["question"], "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"], "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "filter": question.get("filter"), "filter_applied": filt,
        "hit@1": first_hit == 1, "hit@3": first_hit is not None and first_hit <= 3,
        "first_hit_rank": first_hit, "failure": failure,
        # Whether all top-k respect the question's scope, regardless of whether a filter was sent.
        "filter_compliant": None if required is None else all(r["chapter"] == required for r in ranked),
        "manual_override": None,
        "top_k": ranked,
    }


def _ratio(n: int, total: int) -> dict[str, Any]:
    return {"n": n, "N": total, "pct": round(100 * n / total, 1) if total else None}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Hit@1, Evidence Hit@3 and filter compliance as n/N per config x split."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t in traces:
        groups[(t["config"], t["split"])].append(t)
    summary = {}
    for (config, split), items in sorted(groups.items()):
        scoped = [t for t in items if t["filter_compliant"] is not None]
        summary[f"{config}/{split}"] = {
            "config": config, "split": split,
            "hit@1": _ratio(sum(t["hit@1"] for t in items), len(items)),
            "hit@3": _ratio(sum(t["hit@3"] for t in items), len(items)),
            "filter_compliance": _ratio(sum(t["filter_compliant"] for t in scoped), len(scoped)) if scoped else "N/A",
            "failures": dict(sorted(
                {f: sum(t["failure"] == f for t in items) for f in {t["failure"] for t in items} if f}.items())),
        }
    return summary
