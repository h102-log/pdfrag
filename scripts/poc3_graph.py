r"""PoC3 runner: pump_manual.md -> load -> chunk -> extract (Claude) -> Neo4j.

Run from the repo root in PowerShell (NOT git-bash: unstructured/torch can
segfault there). The loader for .md does not touch unstructured, so this script
is usually safe either way, but PowerShell stays the recommended shell:

    backend\.venv\Scripts\python.exe scripts\poc3_graph.py

Prerequisites:
    - docker compose up -d           (Neo4j on bolt://localhost:7687)
    - real ANTHROPIC_API_KEY in backend/.env

Verify (Gate 1): open Neo4j Browser http://localhost:7474 and run
    MATCH (n)-[r]->(m) RETURN n, r, m
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# allow `import app.*` when run as a loose script (no install needed)
sys.path.insert(0, str(ROOT / "backend"))

from app.chunking.chunker import chunk_document          # noqa: E402
from app.graph.extractor import build_extractor, build_llm  # noqa: E402
from app.graph.store import build_index, build_store, chunks_to_nodes  # noqa: E402
from app.loaders.router import load                       # noqa: E402

SAMPLE = ROOT / "samples" / "pump_manual.md"


def main() -> None:
    print(f"[1/4] load + chunk: {SAMPLE.name}")
    doc = load(SAMPLE)
    chunks = chunk_document(doc)
    nodes = chunks_to_nodes(chunks)
    print(f"      {len(chunks)} chunks -> {len(nodes)} source nodes")

    print("[2/4] build Claude extractor + Neo4j store")
    llm = build_llm()
    extractor = build_extractor(llm)
    store = build_store()

    print("[3/4] extract triplets + load into Neo4j (calls Claude, may take ~30s)...")
    build_index(nodes, extractor, store, llm)

    print("[4/4] graph summary:")
    n_nodes = store.structured_query("MATCH (n) RETURN count(n) AS c")[0]["c"]
    n_rels = store.structured_query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    print(f"      nodes={n_nodes}  relationships={n_rels}")

    sample = store.structured_query(
        "MATCH (a)-[r]->(b) WHERE a.name IS NOT NULL AND b.name IS NOT NULL "
        "RETURN a.name AS s, type(r) AS p, b.name AS o LIMIT 25"
    )
    print("      sample triplets:")
    for row in sample:
        print(f"        ({row['s']}) -[{row['p']}]-> ({row['o']})")

    if n_rels == 0:
        print(
            "\n[warn] 0 relationships extracted. Under-extraction is the known trap — "
            "retry, raise max_triplets_per_chunk, or add rule-based fallbacks (W3)."
        )
    else:
        print("\n[ok] Gate 1 graph slice ready. Visualize in Neo4j Browser.")


if __name__ == "__main__":
    main()
