"""Read and normalize source data."""
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .models import DocumentPage

logger = logging.getLogger(__name__)

# OpenStax running headers/footers, e.g. "8     1 • An Introduction to Sociology",
# "1.1 • What Is Sociology?     9", "Access for free at openstax.org".
_FOOTER_PATTERNS = [
    re.compile(r"^\d+\s+\d+ • .+$"),
    re.compile(r"^\d+\.\d+ • .+\s+\d+$"),
    re.compile(r"^Access for free at openstax\.org$"),
]
_SECTION_HEADING = re.compile(r"^(\d+\.\d+) [A-Z].*$")
_BLOCK_START = re.compile(r"^(•|FIGURE \d|TABLE \d|\d+\. |\d+\.\d+ [A-Z])")
_TERMINAL = tuple(".?!:;”\")]’")
_KEEP_UPPER = {"LEARNING OBJECTIVES"}


def load_pdf(
    path: Path, document_id: str, source: str, pages: list[int] | None = None
) -> list[DocumentPage]:
    """Extract raw text per physical page (1-based). Empty/failed pages are kept and flagged."""
    reader = PdfReader(str(path))
    numbers = pages or list(range(1, len(reader.pages) + 1))
    result = []
    for number in numbers:
        metadata: dict[str, Any] = {}
        try:
            text = reader.pages[number - 1].extract_text() or ""
        except Exception as exc:  # pypdf raises many types on broken pages
            text = ""
            metadata["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("page %s: extraction failed: %s", number, exc)
        if not text.strip():
            metadata["empty"] = True
            logger.warning("page %s: no extractable text", number)
        result.append(DocumentPage(document_id, source, number, text, metadata))
    return result


def _is_noise(line: str) -> bool:
    if any(p.match(line) for p in _FOOTER_PATTERNS):
        return True
    # Callout labels such as "SOCIOLOGY IN THE REAL WORLD", "BIG PICTURE".
    return line.isupper() and len(line) <= 40 and line not in _KEEP_UPPER


def _ends_paragraph(line: str, next_line: str, width: int) -> bool:
    if _BLOCK_START.match(next_line) or next_line in _KEEP_UPPER or line in _KEEP_UPPER:
        return True
    if _SECTION_HEADING.match(line):
        return True
    short = len(line) < 0.75 * width
    if short and line.endswith(_TERMINAL):
        return True
    # Heading: short line, no sentence punctuation.
    return len(line) < 0.6 * width and line[:1].isupper() and not line.endswith(",")


def normalize_text(text: str) -> str:
    """NFKC, drop running headers/callout labels, rebuild paragraphs separated by blank lines.

    Curly quotes and dashes are kept so evidence quotes still match the source.
    """
    text = unicodedata.normalize("NFKC", text)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l and not _is_noise(l)]
    if not lines:
        return ""
    width = max(len(l) for l in lines)
    paragraphs: list[str] = []
    current = ""
    for i, line in enumerate(lines):
        if current.endswith("-") and line[:1].islower():
            current += line  # hyphenated compound broken across lines
        else:
            current = f"{current} {line}" if current else line
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if not next_line or _ends_paragraph(line, next_line, width):
            paragraphs.append(current)
            current = ""
    return "\n\n".join(paragraphs)


def _section_markers(text: str) -> list[tuple[int, str]]:
    """Section starts are headings like '1.2 The History...' followed by LEARNING OBJECTIVES.

    This skips the chapter outline list, which uses the same numbering.
    """
    markers = []
    for m in re.finditer(r"(?m)^(\d+\.\d+) [A-Z][^\n]*\n\nLEARNING OBJECTIVES", text):
        markers.append((m.start(), m.group(1)))
    return markers


def load_corpus(manifest_path: Path, base_dir: Path | None = None) -> tuple[list[DocumentPage], dict]:
    """Load only the manifest's counted pages, normalized, with chapter/section metadata."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = base_dir or manifest_path.resolve().parent.parent
    pages: list[DocumentPage] = []
    log: dict[str, Any] = {"empty_pages": [], "error_pages": [], "pages": []}
    for src in manifest["sources"]:
        for scope in src["selected_scope"]:
            chapter, title = scope["chapter"], scope["title"]
            raw_pages = load_pdf(base_dir / src["local_path"], src["source_id"],
                                 src["source_path_or_url"], scope["pdf_pages"])
            section = f"{chapter}.0"  # chapter introduction before the first section
            for page in raw_pages:
                # Chapter opener footer, e.g. "1 An Introduction to Sociology".
                ra=w = "\n".join(l for l in page.text.splitlines() if l.strip() != f"{chapter} {title}")
                page.text = normalize_text(raw)
                markers = _section_markers(page.text)
                page.metadata.update({
                    "chapter": chapter,
                    "chapter_title": title,
                    "section_at_start": section,
                    "section_markers": markers,
                })
                if markers:
                    section = markers[-1][1]
                if page.metadata.get("empty"):
                    log["empty_pages"].append(page.page)
                if page.metadata.get("error"):
                    log["error_pages"].append({"page": page.page, "error": page.metadata["error"]})
                log["pages"].append({"page": page.page, "chapter": chapter,
                                     "chars": len(page.text), "paragraphs": page.text.count("\n\n") + 1})
                pages.append(page)
    log["page_count"] = len(pages)
    log["content_pages"] = sum(1 for p in pages if p.text)
    log["total_chars"] = sum(len(p.text) for p in pages)
    return pages, log
