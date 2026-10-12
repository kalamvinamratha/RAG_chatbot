import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import postgres
from app.db.models import Base
from app.db.postgres import get_db
from app.main import app


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(
        settings, "API_KEYS", {"admin": "test-admin-key", "other": "test-other-key"}
    )
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    # Services cache provider keys at import time, before fixtures execute.
    from app.ingestion.entity_extractor import medical_extractor
    from app.ingestion.pipeline import ingestion_pipeline
    from app.rag.embeddings import embedding_service
    from app.rag.follow_up_generator import follow_up_generator
    from app.rag.generator import rag_coordinator

    for service in (
        medical_extractor,
        ingestion_pipeline.multimodal_processor,
        embedding_service,
        follow_up_generator,
        rag_coordinator,
    ):
        monkeypatch.setattr(service, "api_key", None)
        if hasattr(service, "gemini_api_key"):
            monkeypatch.setattr(service, "gemini_api_key", None)
        if hasattr(service, "openai_api_key"):
            monkeypatch.setattr(service, "openai_api_key", None)
        if hasattr(service, "groq_api_key"):
            monkeypatch.setattr(service, "groq_api_key", None)


@pytest.fixture
async def session_factory(monkeypatch, tmp_path):
    from app.api.v1 import chat

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(postgres, "engine", engine)
    monkeypatch.setattr(postgres, "AsyncSessionLocal", factory)
    monkeypatch.setattr(chat, "AsyncSessionLocal", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await postgres.init_db()
    yield factory
    await engine.dispose()


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
async def api_client(session_factory):
    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test-admin-key"},
    ) as client:
        yield client
    app.dependency_overrides.clear()
