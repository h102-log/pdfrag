from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title="GraphRAG Multi-format Q&A", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": settings.anthropic_model,
        "qdrant": settings.qdrant_url,
        "neo4j": settings.neo4j_uri,
    }


# W5+: mount routers here
# from app.routers import upload, chat, documents, graph, sessions
# app.include_router(upload.router)
