import asyncio
import logging

from app.db.postgres import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("Initializing PostgreSQL schema and default domain agents in hybrid_rag...")
    try:
        await init_db()
        logger.info("Database tables and seed agents initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to connect or initialize database 'hybrid_rag': {e}")
        logger.info("Please ensure PostgreSQL is running and credentials in .env are correct.")


if __name__ == "__main__":
    asyncio.run(main())
