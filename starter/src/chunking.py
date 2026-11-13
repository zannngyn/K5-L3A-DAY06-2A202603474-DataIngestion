"""Implement fixed-size and structure-aware chunking."""
import re

from .models import Chunk, DocumentPage

_SENTENCE_END = re.compile(r"(?<=[.!?”])\s+(?=[A-Z“(])")
_TERMINAL = tuple(".?!:;”\")]’")


def _section_at(page: DocumentPage, offset: int) -> str | None:
    section = page.metadata.get("section_at_start")
    for start, sid in page.metadata.get("section_markers", []):
        if start <= offset:
            section = sid
    return section


def _make_chunk(page: DocumentPage, strategy: str, index: int, start: int, end: int) -> Chunk:
    meta = {k: v for k, v in page.metadata.items() if k not in ("section_markers", "section_at_start")}
    meta.update({"strategy": strategy, "section": _section_at(page, start),
                 "char_start": start, "char_end": end})
    return Chunk(
        chunk_id=f"{page.document_id}-p{page.page:03d}-{strategy}-{index:03d}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=page.text[start:end],
        metadata=meta,
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Character windows of `size` with `overlap`; may cut mid-word by design (baseline A)."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError(f"invalid size/overlap: {size}/{overlap}")
    text = page.text
    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(_make_chunk(page, "fixed", len(chunks), start, end))
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", text)]


def _split_long(text: str, start: int, end: int, max_size: int) -> list[tuple[int, int]]:
    """Split one oversized paragraph at sentence boundaries; hard-cut single huge sentences."""
    cuts = [start] + [start + m.end() for m in _SENTENCE_END.finditer(text[start:end])] + [end]
    sentences = [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]
    spans: list[tuple[int, int]] = []
    cur_start, cur_end = sentences[0]
    for a, b in sentences[1:]:
        if b - cur_start <= max_size:
            cur_end = b
        else:
            spans.append((cur_start, cur_end))
            cur_start, cur_end = a, b
    spans.append((cur_start, cur_end))
    result = []
    for a, b in spans:
        while b - a > max_size:
            result.append((a, a + max_size))
            a += max_size
        result.append((a, b))
    return [(a, b) for a, b in result if text[a:b].strip()]


def _is_heading(paragraph: str) -> bool:
    return len(paragraph) < 80 and not paragraph.endswith(_TERMINAL)


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Pack whole paragraphs up to `max_size`; headings stay with the following paragraph.

    A carried heading (< 80 chars) may push a chunk slightly past `max_size`.
    """
    text = page.text
    units: list[tuple[int, int]] = []
    for a, b in _paragraph_spans(text):
        units.extend(_split_long(text, a, b, max_size) if b - a > max_size else [(a, b)])

    groups: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for unit in units:
        if current and unit[1] - current[0][0] > max_size:
            # Do not leave a heading dangling at the end of a chunk.
            carry = []
            while len(current) > 1 and _is_heading(text[current[-1][0]:current[-1][1]]):
                carry.insert(0, current.pop())
            groups.append(current)
            current = carry
        current.append(unit)
    if current:
        groups.append(current)
    return [_make_chunk(page, "para", i, g[0][0], g[-1][1]) for i, g in enumerate(groups)]


# Single source of chunking parameters for every script. Config C reuses B's chunks.
STRATEGIES = {
    "A": lambda page: fixed_size(page, size=500, overlap=50),
    "B": lambda page: by_paragraph(page, max_size=800),
}
