"""Common loader schema. Every loader normalizes to LoadedDoc -> list[Element].

Location semantics per format (개발계획서 6.1):
  PDF   -> page    (e.g. "p.1")
  MD/HTML -> section (heading path)
  DOCX/PPTX -> section/slide
  TXT   -> offset   (char offset)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ElementType = Literal["text", "table"]


@dataclass
class Element:
    """One normalized chunk-candidate: a text block or a table."""

    type: ElementType
    content: str
    location: str  # page / section / offset — format-specific, kept end-to-end
    meta: dict = field(default_factory=dict)


@dataclass
class LoadedDoc:
    """Result of loading one source file, before chunking."""

    doc_id: str
    doc_name: str
    doc_type: str  # md | pdf | txt | docx | xlsx | pptx | html ...
    file_path: str
    elements: list[Element] = field(default_factory=list)

    @property
    def download_url(self) -> str:
        return f"/api/documents/{self.doc_id}/download"

    def summary(self) -> dict:
        n_text = sum(1 for e in self.elements if e.type == "text")
        n_table = sum(1 for e in self.elements if e.type == "table")
        return {
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "doc_type": self.doc_type,
            "elements": len(self.elements),
            "text": n_text,
            "table": n_table,
        }


def make_doc_id(path: str | Path) -> str:
    """Stable short id from absolute path."""
    p = str(Path(path).resolve())
    return hashlib.sha1(p.encode("utf-8")).hexdigest()[:12]
