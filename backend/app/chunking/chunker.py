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


def _split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Greedy pack sentences up to max_chars; carry overlap tail into next chunk."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    sents = [s for s in _SENT.split(text) if s and s.strip()]
    if not sents:  # no boundaries -> hard window
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars - overlap)]
    chunks: list[str] = []
    cur = ""
    for s in sents:
        s = s.strip()
        if cur and len(cur) + 1 + len(s) > max_chars:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            cur = (tail + " " + s).strip() if tail else s
        else:
            cur = (cur + " " + s).strip() if cur else s
    if cur:
        chunks.append(cur)
    return chunks


def _split_table(md: str, max_chars: int) -> list[str]:
    """Split an oversized table by rows, repeating header into each part."""
    if len(md) <= max_chars:
        return [md]
    lines = md.splitlines()
    # markdown table: header + separator are first two lines (best effort)
    header = lines[:2] if len(lines) >= 2 and lines[1].lstrip().startswith("|") else []
    body = lines[len(header):]
    parts: list[str] = []
    cur = list(header)
    cur_len = sum(len(x) for x in cur)
    for row in body:
        if cur_len + len(row) > max_chars and len(cur) > len(header):
            parts.append("\n".join(cur))
            cur = list(header)
            cur_len = sum(len(x) for x in cur)
        cur.append(row)
        cur_len += len(row)
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
