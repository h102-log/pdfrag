"""PDF loader via PyMuPDF. Extracts per-page text and tables (table-aware)."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.loaders.base import Element, LoadedDoc, make_doc_id


def _rect_tuple(r) -> tuple[float, float, float, float]:
    """Normalize a fitz.Rect or (x0, y0, x1, y1) sequence to a float 4-tuple."""
    if isinstance(r, (tuple, list)):
        return float(r[0]), float(r[1]), float(r[2]), float(r[3])
    return float(r.x0), float(r.y0), float(r.x1), float(r.y1)


def _intersects(a: tuple, b: tuple) -> bool:
    """True only on positive-area overlap (touching edges do not count)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _text_outside_tables(blocks, table_rects) -> str:
    """Join the text of page blocks that do not fall inside any table rect.

    ``blocks`` are PyMuPDF ``page.get_text("blocks")`` tuples
    (x0, y0, x1, y1, text, ...). Dropping blocks that intersect a detected
    table prevents table cell values from entering the graph twice (once as a
    Table element, again inside the page text).
    """
    rects = [_rect_tuple(r) for r in table_rects]
    out: list[str] = []
    for b in blocks:
        text = (b[4] or "").strip()
        if not text:
            continue
        block_rect = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        if any(_intersects(block_rect, tr) for tr in rects):
            continue
        out.append(text)
    return "\n".join(out)


def _table_to_md(rows: list[list]) -> str:
    """Render extracted table rows as markdown so row/col context survives."""
    clean = [[("" if c is None else str(c)).strip() for c in r] for r in rows]
    if not clean:
        return ""
    head = clean[0]
    body = clean[1:]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def load_pdf(path: str | Path) -> LoadedDoc:
    path = Path(path)
    doc = fitz.open(path)
    elements: list[Element] = []
    try:
        for page in doc:  # type: ignore[assignment]
            loc = f"p.{page.number + 1}"
            # tables first (table-aware: keep each table as one element)
            table_rects = []
            try:
                tabs = page.find_tables()
            except Exception:
                tabs = None
            if tabs and tabs.tables:
                for t in tabs.tables:
                    md = _table_to_md(t.extract())
                    if md:
                        elements.append(Element("table", md, loc, {"bbox": list(t.bbox)}))
                        table_rects.append(fitz.Rect(t.bbox))
            # page text with the table regions removed so cell values are not
            # duplicated (Table element + page text). No tables -> keep all text.
            if table_rects:
                text = _text_outside_tables(page.get_text("blocks"), table_rects)
            else:
                text = page.get_text("text").strip()
            if text:
                elements.append(Element("text", text, loc))
    finally:
        doc.close()
    return LoadedDoc(
        doc_id=make_doc_id(path),
        doc_name=path.name,
        doc_type="pdf",
        file_path=str(path.resolve()),
        elements=elements,
    )
