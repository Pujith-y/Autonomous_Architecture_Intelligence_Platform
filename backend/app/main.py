from fastapi import FastAPI
from app.config.settings import settings
from app.core.logger import logger
from contextlib import asynccontextmanager

from app.database.postgres import check_postgres_connection
from app.database.neo4j import check_neo4j_connection
from app.database.qdrant import check_qdrant_connection

logger.info("AAIP Started")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AAIP...")

    if check_postgres_connection():
        logger.info("✅ PostgreSQL connected")
    else:
        logger.error("❌ PostgreSQL connection failed")

    if check_neo4j_connection():
        logger.info("✅ Neo4j connected")
    else:
        logger.error("❌ Neo4j connection failed")

    if check_qdrant_connection():
        logger.info("✅ Qdrant connected")
    else:
        logger.error("❌ Qdrant connection failed")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION
)

@app.get("/")
def root():
    return {
        "message": "AAIP is running"
    }

@app.get("/health")
def health():
    postgres_ok = check_postgres_connection()
    neo4j_ok = check_neo4j_connection()
    qdrant_ok = check_qdrant_connection()

    overall = (
        "healthy"
        if postgres_ok and neo4j_ok and qdrant_ok
        else "degraded"
    )

    return {
        "status": overall,
        "services": {
            "postgres": "healthy" if postgres_ok else "unhealthy",
            "neo4j": "healthy" if neo4j_ok else "unhealthy",
            "qdrant": "healthy" if qdrant_ok else "unhealthy",
        },
    }