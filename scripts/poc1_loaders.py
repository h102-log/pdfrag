"""PoC ①: load MD + DOCX + PDF through the router, show text/table/location."""
from pathlib import Path

from app.loaders.router import load

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
FILES = ["pump_manual.md", "pump_report.docx", "pump_spec.pdf"]


def main() -> None:
    for name in FILES:
        doc = load(SAMPLES / name)
        print("=" * 70)
        print(doc.summary())
        print("download_url:", doc.download_url)
        for i, el in enumerate(doc.elements):
            preview = el.content.replace("\n", " ")[:90]
            print(f"  [{i}] {el.type:5} @ {el.location:14} | {preview}")
        # show one full table if present
        tbl = next((e for e in doc.elements if e.type == "table"), None)
        if tbl:
            print("  --- first table ---")
            print("  " + tbl.content.replace("\n", "\n  "))


if __name__ == "__main__":
    main()
