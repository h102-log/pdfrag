"""Loader router: dispatch by extension. PDF->PyMuPDF, MD/TXT->text, rest->Unstructured."""
from __future__ import annotations

from pathlib import Path

from app.loaders.base import LoadedDoc

# .eml is intentionally absent: the installed Unstructured build exposes no
# email extra, so .eml is unsupported for now (not in the W1 sample set).
_UNSTRUCTURED_EXT = {".docx", ".xlsx", ".pptx", ".html", ".htm"}


def load(path: str | Path) -> LoadedDoc:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        from app.loaders.pdf_loader import load_pdf

        return load_pdf(path)
    if ext in {".md", ".markdown"}:
        from app.loaders.text_loader import load_markdown

        return load_markdown(path)
    if ext == ".txt":
        from app.loaders.text_loader import load_text

        return load_text(path)
    if ext in _UNSTRUCTURED_EXT:
        from app.loaders.unstructured_loader import load_unstructured

        return load_unstructured(path)
    raise ValueError(f"unsupported extension: {ext}")
