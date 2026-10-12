import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.db.neo4j_client import neo4j_service
from app.db.postgres import engine, init_db
from app.db.qdrant_client import qdrant_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Initializing Healthcare AI Backend services...")
    try:
        await init_db()
    except Exception as e:
        logger.warning("PostgreSQL init warning (check if database is accessible): %s", e)

    try:
        await qdrant_service.init_collection()
    except Exception as e:
        logger.warning("Qdrant init warning: %s", e)

    try:
        await neo4j_service.init_schema()
    except Exception as e:
        logger.warning("Neo4j init warning: %s", e)

    yield

    # Shutdown sequence
    logger.info("Closing backend database connections...")
    await qdrant_service.close()
    await neo4j_service.close()
    await engine.dispose()
    logger.info("Healthcare AI Backend services stopped.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Backend service for Healthcare AI Hybrid Graph RAG Chatbot with domain agents, multi-format ingestion, and multi-modal knowledge retrieval.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health status check endpoint for database, vector store, and graph connectors."""
    services_status = {
        "status": "unhealthy",
        "database": "unknown",
        "qdrant": "unknown",
        "neo4j": "unknown",
        "environment": settings.ENVIRONMENT,
    }

    # Check Postgres
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            services_status["database"] = "connected"
    except Exception as e:
        logger.warning("Database health check failed: %s", e)
        services_status["database"] = "unreachable"

    # Check Qdrant
    try:
        client = await qdrant_service.connect()
        await client.get_collections()
        services_status["qdrant"] = "connected"
    except Exception as e:
        logger.warning("Qdrant health check failed: %s", e)
        services_status["qdrant"] = "unreachable"

    # Check Neo4j
    try:
        await neo4j_service.run_query("RETURN 1 AS ping")
        services_status["neo4j"] = "connected"
    except Exception as e:
        logger.warning("Neo4j health check failed: %s", e)
        services_status["neo4j"] = (
            "fallback" if neo4j_service.fallback_store is not None else "unreachable"
        )

    healthy = all(
        services_status[k] in ("connected", "fallback") for k in ("database", "qdrant", "neo4j")
    )
    services_status["status"] = "healthy" if healthy else "unhealthy"
    return JSONResponse(services_status, status_code=200 if healthy else 503)
