from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env regardless of the process working directory (repo root, backend/, ...)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# repo-root storage/files (what docker-compose mounts at ./storage), anchored to
# this file so it is independent of the process working directory.
# parents[2] = backend/, parents[3] = repo root.
_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "files"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # LLM / embedding
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    embed_model: str = "text-embedding-3-small"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "graphrag123"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "graphrag"

    # Postgres
    database_url: str = "postgresql+psycopg://graphrag:graphrag123@localhost:5432/graphrag"

    # Storage
    storage_dir: str = str(_STORAGE_DIR)


settings = Settings()
