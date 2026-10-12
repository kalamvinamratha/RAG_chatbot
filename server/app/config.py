from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find root .env file
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Healthcare AI Hybrid Graph RAG"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "temporary-secret-key-for-development"
    API_KEYS: dict[str, str] = {}  # owner ID -> private API key
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    UPLOAD_DIR: Path = ROOT_DIR / "server" / "uploads"

    # PostgreSQL Database (User-specified database: hybrid_rag)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "hybrid_rag"
    DATABASE_URL: str | None = None

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            # Ensure asyncpg driver
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Qdrant Vector Store
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_HTTPS: bool | None = None
    QDRANT_COLLECTION_NAME: str = "healthcare_knowledge"
    EMBEDDING_DIMENSION: int = 768  # Standard medical/text embedding dimension

    # Neo4j Knowledge Graph
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password123"

    # LLM Providers
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    GROQ_MODEL_NAME: str = "openai/gpt-oss-120b"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Voice / Whisper
    VOICE_TRANSCRIBE_PROVIDER: str = "groq"


@lru_cache
def get_settings() -> Settings:
    return Settings()
