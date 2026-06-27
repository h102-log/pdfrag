"""Chunker invariants (RED) + behavior-locking characterization tests.

Invariants under test:
  INV-A: every text chunk len <= max_chars (long sentence is hard-windowed).
  INV-B: the overlap seed for the next chunk also respects max_chars.
  INV-C: overlap carried forward is whole trailing sentence(s), never a
         mid-syllable character slice.
  INV-D: no empty/whitespace-only chunk is produced.
  INV-E: table row-split accounts for the newline join characters.
  #2   : an oversized HTML table is row-split on <tr> boundaries.

Characterization (must NOT change): small table stays one chunk, source meta
propagates to every chunk, sentence packing stays greedy, oversized markdown
table repeats its header into every part.
"""
import re

from app.chunking import chunker
from app.loaders.base import Element, LoadedDoc


# --- helpers --------------------------------------------------------------
def _doc(elements, doc_id="D1", name="n.md", dtype="md", path="/abs/n.md"):
    return LoadedDoc(doc_id=doc_id, doc_name=name, doc_type=dtype,
                     file_path=path, elements=elements)


# --- INV-A: every chunk <= max_chars -------------------------------------
def test_single_long_sentence_is_hard_windowed():
    # one sentence (no internal boundary) far over the budget
    text = "a" * 1000 + "."
    chunks = chunker._split_text(text, max_chars=100, overlap=20)
    assert chunks, "must produce at least one chunk"
    assert all(len(c) <= 100 for c in chunks)


def test_no_boundary_text_stays_within_budget():
    text = "x" * 1000  # no sentence enders at all
    chunks = chunker._split_text(text, max_chars=100, overlap=20)
    assert all(len(c) <= 100 for c in chunks)


# --- INV-B: overlap seed respects max_chars ------------------------------
def test_overlap_seed_never_exceeds_max():
    # near-budget sentences + large overlap: old code's (tail + s) seed blew
    # past max_chars; the guarantee/headroom logic must keep every chunk <= max.
    sents = [c * 40 + "." for c in "abcdefgh"]  # each 41 chars
    text = " ".join(sents)
    chunks = chunker._split_text(text, max_chars=50, overlap=45)
    assert all(len(c) <= 50 for c in chunks)


# --- INV-C: overlap is a whole sentence, not a mid-word slice -------------
def test_overlap_is_whole_sentence_not_midword():
    sents = [f"S{i} aa bb cc dd." for i in range(1, 8)]  # each 15 chars
    text = " ".join(sents)
    chunks = chunker._split_text(text, max_chars=50, overlap=30)
    assert len(chunks) >= 2, "input must span multiple chunks to exercise overlap"
    # every chunk after the first must begin at a sentence boundary (S<digit>),
    # not in the middle of the previous chunk's trailing word.
    for c in chunks[1:]:
        assert re.match(r"^S\d", c), f"chunk starts mid-word from overlap: {c!r}"


# --- INV-D: no empty chunks ----------------------------------------------
def test_split_table_empty_returns_empty_list():
    assert chunker._split_table("", 800) == []
    assert chunker._split_table("   \n  ", 800) == []


def test_whitespace_text_element_yields_no_chunk():
    doc = _doc([Element("text", "   \n\t  ", "section:A")])
    assert chunker.chunk_document(doc) == []


def test_empty_table_element_yields_no_chunk():
    doc = _doc([Element("table", "", "section:A")])
    assert chunker.chunk_document(doc) == []


# --- INV-E: table split counts the newline join chars --------------------
def test_table_split_accounts_for_newlines():
    header = "| H |\n|---|"          # two header lines
    rows = "\n".join(["| a |"] * 30)  # 30 body rows
    md = header + "\n" + rows
    parts = chunker._split_table(md, 100)
    assert len(parts) >= 2
    # the real (joined) length of every part must respect the budget
    assert all(len(p) <= 100 for p in parts)
    # header repeated into every part
    assert all(p.startswith("| H |\n|---|") for p in parts)


# --- #2: oversized HTML table is row-split on <tr> -----------------------
def test_html_table_is_row_split():
    header = "<tr><th>Name</th><th>Value</th></tr>"
    body = "".join(
        f"<tr><td>item{i}</td><td>{'x' * 20}</td></tr>" for i in range(40)
    )
    html = f"<table>{header}{body}</table>"
    assert len(html) > 300
    parts = chunker._split_table(html, 300)
    assert len(parts) >= 2, "oversized HTML table must split into multiple parts"
    for p in parts:
        # each part stays valid table structure with the header repeated
        assert "<table" in p and "</table>" in p
        assert "<th>Name</th>" in p
        # within budget, or an unavoidable single body row (header + 1 row)
        assert len(p) <= 300 or p.count("<tr") <= 2


# --- characterization: small table stays a single chunk ------------------
def test_small_table_stays_single_chunk():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    assert chunker._split_table(md, 800) == [md]
    doc = _doc([Element("table", md, "section:T", {"category": "Table"})])
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.is_table is True
    assert c.content == md
    assert c.meta["split"] is False


# --- characterization: source meta propagates everywhere -----------------
def test_source_meta_propagates_to_every_chunk():
    longtext = " ".join(f"S{i} word word word word word." for i in range(1, 40))
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    doc = _doc(
        [Element("text", longtext, "section:A"),
         Element("table", table, "section:B", {"category": "Table"})],
        doc_id="DOC9", name="report.pdf", dtype="pdf", path="/files/report.pdf",
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 3  # text splits into >1 + the table
    for c in chunks:
        assert c.doc_id == "DOC9"
        assert c.doc_name == "report.pdf"
        assert c.doc_type == "pdf"
        assert c.file_path == "/files/report.pdf"
        assert c.download_url == "/api/documents/DOC9/download"
        assert c.location in {"section:A", "section:B"}
    table_chunks = [c for c in chunks if c.is_table]
    assert len(table_chunks) == 1
    assert table_chunks[0].location == "section:B"


# --- characterization: greedy sentence packing ---------------------------
def test_sentence_packing_is_greedy():
    sents = [f"S{i} alpha beta gamma." for i in range(1, 7)]  # each ~20 chars
    text = " ".join(sents)
    chunks = chunker._split_text(text, max_chars=100, overlap=10)
    # multiple short sentences must pack into one chunk (not one-per-chunk)
    assert "S1" in chunks[0] and "S2" in chunks[0]


# --- characterization: oversized markdown table repeats header -----------
def test_oversized_markdown_table_repeats_header():
    header = "| col1 | col2 |\n| --- | --- |"
    rows = "\n".join(f"| r{i}a | r{i}b |" for i in range(60))
    md = header + "\n" + rows
    parts = chunker._split_table(md, 200)
    assert len(parts) >= 2
    for p in parts:
        assert p.startswith(header)
