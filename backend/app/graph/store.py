"""Neo4j property-graph store + index builder for PoC3.

Source backlink (개발계획서 요구): each chunk becomes a source node carrying
doc_id / location / chunk_id; extracted entities link back to it (LlamaIndex
emits a MENTIONS edge chunk -> entity). The chunk node id IS the chunk_id, so
the same key joins this graph to the future Qdrant vectors — that bidirectional
graph<->vector ID linkage is what W2+ retrieval builds on.
"""
from __future__ import annotations

from collections.abc import Sequence

from llama_index.core import PropertyGraphIndex
from llama_index.core.schema import BaseNode, TextNode
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.llms.anthropic import Anthropic

from app.chunking.chunker import Chunk
from app.core.config import settings


def build_store() -> Neo4jPropertyGraphStore:
    """Neo4j property-graph store from settings (.env / docker compose defaults)."""
    return Neo4jPropertyGraphStore(
        username=settings.neo4j_user,
        password=settings.neo4j_password,
        url=settings.neo4j_uri,
    )


def chunks_to_nodes(chunks: list[Chunk]) -> list[TextNode]:
    """Chunk -> LlamaIndex TextNode. chunk_id becomes the node id (graph<->vector key)."""
    nodes: list[TextNode] = []
    for c in chunks:
        nodes.append(
            TextNode(
                id_=c.chunk_id,
                text=c.content,
                metadata={
                    "doc_id": c.doc_id,
                    "doc_name": c.doc_name,
                    "doc_type": c.doc_type,
                    "location": c.location,      # 출처 표기용 위치 메타 (page/section/offset)
                    "chunk_id": c.chunk_id,
                    "is_table": c.is_table,
                    "download_url": c.download_url,
                },
                # keep meta out of the LLM extraction text; it is structural, not content
                excluded_llm_metadata_keys=[
                    "doc_id", "doc_name", "doc_type", "location",
                    "chunk_id", "is_table", "download_url",
                ],
            )
        )
    return nodes


def build_index(
    nodes: Sequence[BaseNode],
    extractor: object,
    store: Neo4jPropertyGraphStore,
    llm: Anthropic,
) -> PropertyGraphIndex:
    """Run extraction + load into Neo4j. No embeddings in PoC3 (embed_kg_nodes=False),
    so no OPENAI_API_KEY is required at this stage."""
    return PropertyGraphIndex(
        nodes=list(nodes),
        llm=llm,
        kg_extractors=[extractor],          # type: ignore[list-item]
        property_graph_store=store,
        embed_kg_nodes=False,               # PoC3: skip vectors -> no OpenAI key needed
        use_async=False,                    # Windows-friendly, deterministic for PoC
        show_progress=True,
    )
