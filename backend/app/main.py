from fastapi import FastAPI
from config.settings import settings
from core.logger import logger

logger.info("AAIP Started")

app = FastAPI(
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
    return {
        "status": "healthy"
    }