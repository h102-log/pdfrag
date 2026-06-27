"""Table-aware chunking. Built on loaders (LoadedDoc -> list[Element]).

Rules:
  - table element  -> ALWAYS one chunk, never split (row/col context preserved).
                      Oversized table is row-split but the header row is repeated
                      into every part so each part stays self-describing.
  - text element   -> size-bounded sliding window on sentence/line boundaries,
                      with overlap; never crosses an element/location boundary.
  - every chunk carries full source meta (doc_id/doc_name/doc_type/location/
    file_path/download_url) so 출처 표기·다운로드 연동이 끝까지 가능.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.loaders.base import LoadedDoc

# char-based budget (PoC; token-based swap later). ~800 chars ~= 250-400 tokens KO.
MAX_CHARS = 800
OVERLAP_CHARS = 120
# sentence boundary: CJK/ASCII sentence enders, keep the delimiter
_SENT = re.compile(r"(?<=[.!?。…])\s+|\n{2,}")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_name: str
    doc_type: str
    location: str
    is_table: bool
    content: str
    file_path: str
    download_url: str
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _hard_window(text: str, max_chars: int, overlap: int) -> list[str]:
    """Fixed-size character windows for text that has no usable boundary."""
    step = max(1, max_chars - overlap)
    return [text[i : i + max_chars] for i in range(0, len(text), step)]


def _overlap_tail(sents: list[str], overlap: int, headroom: int) -> str:
    """Whole trailing sentence(s) up to min(overlap, headroom) chars.

    Returning a sentence-aligned tail (never a raw character slice) keeps the
    next chunk from starting mid-word, and capping at ``headroom`` keeps the
    seed (tail + next sentence) within the budget.
    """
    budget = min(overlap, headroom)
    if budget <= 0 or not sents:
        return ""
    tail: list[str] = []
    total = 0
    for s in reversed(sents):
        add = len(s) + (1 if tail else 0)
        if total + add > budget:
            break
        tail.insert(0, s)
        total += add
    return " ".join(tail)


def _split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Greedy-pack sentences up to max_chars; carry a sentence-aligned overlap.

    Guarantees every returned chunk is non-empty and at most ``max_chars``
    long (a single over-long sentence, or any over-long packed chunk, is
    hard-windowed by a final guarantee pass).
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    sents = [s.strip() for s in _SENT.split(text) if s and s.strip()]
    if not sents:  # no usable boundaries -> hard window
        return _hard_window(text, max_chars, overlap)

    chunks: list[str] = []
    cur: list[str] = []  # sentences packed into the current chunk
    cur_len = 0
    for s in sents:
        if len(s) > max_chars:  # a single sentence over budget -> hard window
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_len = [], 0
            chunks.extend(_hard_window(s, max_chars, overlap))
            continue
        add = len(s) + (1 if cur else 0)
        if cur and cur_len + add > max_chars:
            chunks.append(" ".join(cur))
            headroom = max_chars - len(s) - 1  # leave room for the joining space
            tail = _overlap_tail(cur, overlap, headroom)
            cur = [tail, s] if tail else [s]
            cur_len = len(" ".join(cur))
        else:
            cur.append(s)
            cur_len += add
    if cur:
        chunks.append(" ".join(cur))

    # guarantee pass: no emitted chunk may exceed max_chars or be empty
    out: list[str] = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        if len(c) <= max_chars:
            out.append(c)
        else:
            out.extend(w for w in _hard_window(c, max_chars, overlap) if w.strip())
    return out


# HTML table (Unstructured text_as_html): single line, rows in <tr>...</tr>.
_TR = re.compile(r"<tr\b.*?</tr\s*>", re.IGNORECASE | re.DOTALL)


def _looks_like_html_table(s: str) -> bool:
    head = s.lstrip()[:512].lower()
    return head.startswith("<") and ("<table" in head or "<tr" in head)


def _split_html_table(html: str, max_chars: int) -> list[str]:
    """Row-split an oversized HTML table, repeating the first <tr> as header.

    Each part is wrapped in <table>...</table> so it stays a valid, self-
    describing table. A header + single body row that already exceeds the
    budget is emitted as-is (unavoidable oversized row).
    """
    rows = _TR.findall(html)
    if len(rows) <= 1:  # nothing to split on
        return [html]
    header, body = rows[0], rows[1:]
    parts: list[str] = []
    cur = [header]
    for row in body:
        candidate = "<table>" + "".join(cur + [row]) + "</table>"
        if len(cur) > 1 and len(candidate) > max_chars:
            parts.append("<table>" + "".join(cur) + "</table>")
            cur = [header, row]
        else:
            cur.append(row)
    if len(cur) > 1:
        parts.append("<table>" + "".join(cur) + "</table>")
    return parts or [html]


def _split_table(md: str, max_chars: int) -> list[str]:
    """Split an oversized table by rows, repeating the header into each part.

    Empty/whitespace content yields no parts. HTML tables are row-split on
    <tr> boundaries; markdown tables on lines (counting the newline join
    characters so a part never exceeds the budget).
    """
    if not md or not md.strip():
        return []
    if len(md) <= max_chars:
        return [md]
    if _looks_like_html_table(md):
        return _split_html_table(md, max_chars)
    lines = md.splitlines()
    # markdown table: header + separator are the first two lines (best effort)
    header = lines[:2] if len(lines) >= 2 and lines[1].lstrip().startswith("|") else []
    body = lines[len(header):]
    parts: list[str] = []
    cur = list(header)
    for row in body:
        candidate = "\n".join(cur + [row])  # counts the join newlines
        if len(cur) > len(header) and len(candidate) > max_chars:
            parts.append("\n".join(cur))
            cur = list(header)
        cur.append(row)
    if len(cur) > len(header):
        parts.append("\n".join(cur))
    return parts or [md]


def chunk_document(doc: LoadedDoc, max_chars: int = MAX_CHARS,
                   overlap: int = OVERLAP_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0

    def add(content: str, location: str, is_table: bool, meta: dict) -> None:
        nonlocal idx
        chunks.append(Chunk(
            chunk_id=f"{doc.doc_id}:{idx}",
            doc_id=doc.doc_id,
            doc_name=doc.doc_name,
            doc_type=doc.doc_type,
            location=location,
            is_table=is_table,
            content=content,
            file_path=doc.file_path,
            download_url=doc.download_url,
            meta=meta,
        ))
        idx += 1

    for el in doc.elements:
        if el.type == "table":
            for part in _split_table(el.content, max_chars):
                add(part, el.location, True, {**el.meta, "split": len(el.content) > max_chars})
        else:
            for part in _split_text(el.content, max_chars, overlap):
                add(part, el.location, False, dict(el.meta))
    return chunks
