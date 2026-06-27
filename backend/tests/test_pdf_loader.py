"""Unit tests for the pure `_text_outside_tables` helper (no real PDF needed).

The helper takes PyMuPDF `page.get_text("blocks")` tuples (x0, y0, x1, y1,
text, ...) plus the detected table rectangles, and returns the joined text of
blocks that do NOT intersect any table rect, so table cell values do not enter
the graph twice (once as a Table element and again inside the page text).
"""
import pytest

pytest.importorskip("fitz")  # PyMuPDF; skip if the native lib is unavailable

from app.loaders.pdf_loader import _text_outside_tables  # noqa: E402


def test_block_inside_table_is_excluded():
    blocks = [
        (0, 0, 100, 10, "header text"),
        (0, 20, 100, 40, "TABLE CELL DATA"),
        (0, 50, 100, 60, "footer text"),
    ]
    table_rects = [(0, 18, 100, 42)]  # covers the middle block
    out = _text_outside_tables(blocks, table_rects)
    assert "TABLE CELL DATA" not in out
    assert "header text" in out
    assert "footer text" in out
    assert out == "header text\nfooter text"


def test_no_tables_keeps_all_text():
    blocks = [
        (0, 0, 100, 10, "para one"),
        (0, 20, 100, 30, "para two"),
    ]
    out = _text_outside_tables(blocks, [])
    assert out == "para one\npara two"


def test_empty_blocks_are_skipped():
    blocks = [
        (0, 0, 100, 10, "   \n  "),
        (0, 20, 100, 30, "real text"),
    ]
    out = _text_outside_tables(blocks, [])
    assert out == "real text"


def test_partial_overlap_with_table_is_excluded():
    blocks = [(0, 0, 100, 30, "overlapping block")]
    table_rects = [(0, 20, 100, 50)]  # overlaps the bottom of the block
    out = _text_outside_tables(blocks, table_rects)
    assert out == ""


def test_block_touching_table_edge_is_kept():
    # edge-touching (shared boundary, zero-area overlap) is not "inside" a table
    blocks = [(0, 0, 100, 20, "above the table")]
    table_rects = [(0, 20, 100, 40)]
    out = _text_outside_tables(blocks, table_rects)
    assert out == "above the table"
