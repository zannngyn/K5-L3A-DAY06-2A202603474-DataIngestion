"""Build the offline slideshow demo: embed lab results into demo/template.html -> demo/index.html.

Run from starter/: python scripts/build_demo.py
Reads only existing artifacts (results, benchmark, manifest, experiment log); never re-runs retrieval.
"""
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
RESULTS = STARTER / "results"
sys.path.insert(0, str(STARTER))

from src.ingestion import load_corpus, load_pdf  # noqa: E402

SAMPLE_PAGE = 20  # page used to show raw vs normalized text


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return {"header": rows[0], "rows": rows[1:]}


def student_info() -> dict:
    text = (ROOT / "STUDENT.md").read_text(encoding="utf-8")
    fields = {"Họ và tên": "name", "MSSV": "id", "Lớp": "class"}
    info = {}
    for label, key in fields.items():
        m = re.search(rf"^- {re.escape(label)}[^:]*:[ \t]*(.*)$", text, re.M)
        value = (m.group(1).strip() if m else "")
        info[key] = "" if value.startswith("L3A / L3B") else value
    return info


def main() -> None:
    required = [RESULTS / f for f in (
        "traces_dev.jsonl", "traces_test.jsonl", "summary_dev.json", "summary_test.json",
        "run_meta_dev.json", "run_meta_test.json", "ingestion_log.json", "index_runs.jsonl",
        "audit_coherence.csv", "audit_metadata.csv", "audit_grounding.csv")]
    missing = [p.name for p in required if not p.exists()]
    if missing:
        sys.exit(f"Missing results: {missing}. Run export_chunks.py, build_index.py and src.run first.")

    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    source = manifest["sources"][0]
    pages, _ = load_corpus(ROOT / "data" / "manifest.json")
    normalized = next(p.text for p in pages if p.page == SAMPLE_PAGE)
    raw = load_pdf(ROOT / source["local_path"], source["source_id"], source["source_path_or_url"],
                   [SAMPLE_PAGE])[0].text

    with open(ROOT / "artifacts" / "experiment_log.csv", newline="", encoding="utf-8") as f:
        experiment = list(csv.DictReader(f))

    data = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "student": student_info(),
        "source": {k: source[k] for k in ("source_id", "title", "publisher", "source_path_or_url",
                                          "license_or_permission", "attribution", "accessed_at",
                                          "physical_pages_total", "selected_scope", "excluded_pages",
                                          "counted_content_pages", "char_count")},
        "page_counting_rule": manifest["page_counting_rule"],
        "ingestion": json.loads((RESULTS / "ingestion_log.json").read_text(encoding="utf-8")),
        "index_runs": read_jsonl(RESULTS / "index_runs.jsonl"),
        "run_meta": {s: json.loads((RESULTS / f"run_meta_{s}.json").read_text(encoding="utf-8"))
                     for s in ("dev", "test")},
        "summary": {s: json.loads((RESULTS / f"summary_{s}.json").read_text(encoding="utf-8"))
                    for s in ("dev", "test")},
        "questions": json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))["questions"],
        "traces": {s: read_jsonl(RESULTS / f"traces_{s}.jsonl") for s in ("dev", "test")},
        "audits": {name: read_csv(RESULTS / f"audit_{name}.csv")
                   for name in ("coherence", "metadata", "grounding")},
        "experiment": experiment,
        "sample": {"page": SAMPLE_PAGE, "raw": raw, "normalized": normalized},
    }

    template = (ROOT / "demo" / "template.html").read_text(encoding="utf-8")
    marker = "/*__LAB_DATA__*/"
    if template.count(marker) != 1:
        sys.exit("demo/template.html must contain the data marker exactly once")
    # "</" inside a <script> block would end it early; JSON allows the escaped form.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = ROOT / "demo" / "index.html"
    out.write_text(template.replace(marker, payload), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
