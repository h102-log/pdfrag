"""PDF loader via PyMuPDF. Extracts per-page text and tables (table-aware)."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.loaders.base import Element, LoadedDoc, make_doc_id


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
            table_bboxes = []
            try:
                tabs = page.find_tables()
            except Exception:
                tabs = None
            if tabs and tabs.tables:
                for t in tabs.tables:
                    md = _table_to_md(t.extract())
                    if md:
                        elements.append(Element("table", md, loc, {"bbox": list(t.bbox)}))
                        table_bboxes.append(fitz.Rect(t.bbox))
            # page text (kept whole for PoC; chunking happens later)
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
