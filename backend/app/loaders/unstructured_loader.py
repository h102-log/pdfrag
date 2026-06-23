"""DOCX/XLSX/PPTX/HTML/EML loader via Unstructured. Table-aware."""
from __future__ import annotations

from pathlib import Path

from app.loaders.base import Element, LoadedDoc, make_doc_id

# extension -> doc_type
_TYPE = {
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".html": "html",
    ".htm": "html",
    ".eml": "eml",
}


def _location(el, doc_type: str) -> str:
    md = el.metadata
    if doc_type == "pptx" and getattr(md, "page_number", None):
        return f"slide.{md.page_number}"
    if getattr(md, "page_number", None):
        return f"p.{md.page_number}"
    sect = getattr(md, "section", None) or getattr(md, "category_depth", None)
    return f"section:{sect}" if sect is not None else "section:0"


def load_unstructured(path: str | Path) -> LoadedDoc:
    from unstructured.partition.auto import partition

    path = Path(path)
    doc_type = _TYPE.get(path.suffix.lower(), path.suffix.lower().lstrip("."))
    raw = partition(filename=str(path))

    elements: list[Element] = []
    for el in raw:
        cat = getattr(el, "category", "")
        loc = _location(el, doc_type)
        if cat == "Table":
            html = getattr(el.metadata, "text_as_html", None)
            elements.append(Element("table", html or str(el), loc, {"category": cat}))
        else:
            txt = str(el).strip()
            if txt:
                elements.append(Element("text", txt, loc, {"category": cat}))
    return LoadedDoc(make_doc_id(path), path.name, doc_type, str(path.resolve()), elements)
