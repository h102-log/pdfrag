"""MD/TXT loader. MD -> split by heading sections; TXT -> single block w/ offset."""
from __future__ import annotations

import re
from pathlib import Path

from app.loaders.base import Element, LoadedDoc, make_doc_id

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _flush(buf: list[str], section: str, out: list[Element]) -> None:
    """Emit accumulated lines as text/table elements, splitting out md tables."""
    if not buf:
        return
    block: list[str] = []
    in_table = False

    def emit_block():
        nonlocal block
        joined = "\n".join(block).strip()
        if joined:
            kind = "table" if in_table else "text"
            out.append(Element(kind, joined, section))
        block = []

    for line in buf:
        is_row = bool(_TABLE_ROW.match(line))
        if is_row != in_table:
            emit_block()
            in_table = is_row
        block.append(line)
    emit_block()


def load_markdown(path: str | Path) -> LoadedDoc:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    elements: list[Element] = []
    section = path.stem
    buf: list[str] = []
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            _flush(buf, section, elements)
            buf = []
            section = m.group(2).strip()
        else:
            buf.append(line)
    _flush(buf, section, elements)
    return LoadedDoc(make_doc_id(path), path.name, "md", str(path.resolve()), elements)


def load_text(path: str | Path) -> LoadedDoc:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    elements = [Element("text", text.strip(), "offset:0")] if text.strip() else []
    return LoadedDoc(make_doc_id(path), path.name, "txt", str(path.resolve()), elements)
