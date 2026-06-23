"""PoC ②: table-aware chunking over the 3 samples. Verify tables stay intact."""
from pathlib import Path

from app.chunking import chunk_document
from app.loaders.router import load

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
FILES = ["pump_manual.md", "pump_report.docx", "pump_spec.pdf"]


def main() -> None:
    for name in FILES:
        doc = load(SAMPLES / name)
        chunks = chunk_document(doc)
        n_tbl = sum(c.is_table for c in chunks)
        print("=" * 72)
        print(f"{name}: {len(chunks)} chunks ({n_tbl} table)")
        for c in chunks:
            tag = "TABLE" if c.is_table else "text "
            preview = c.content.replace("\n", " ")[:80]
            print(f"  {c.chunk_id:16} {tag} @ {c.location:14} ({len(c.content):4}c) | {preview}")
        # assert: no table chunk lost its delimiters (still markdown/html)
        for c in chunks:
            if c.is_table:
                ok = ("|" in c.content) or ("<table" in c.content)
                assert ok, f"table chunk {c.chunk_id} lost structure"
    print("=" * 72)
    print("PoC2 OK: all table chunks structurally intact")


if __name__ == "__main__":
    main()
