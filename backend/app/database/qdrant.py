from qdrant_client import QdrantClient
from app.core.logger import logger
import time
from app.config.settings import settings

client = QdrantClient(
    host=settings.QDRANT_HOST,
    port=settings.QDRANT_PORT,
)


def check_qdrant_connection(max_retries=10, delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            client.get_collections()
            return True

        except Exception as e:
            logger.warning(
                f"Qdrant not ready (attempt {attempt}/{max_retries}): {e}"
            )
            time.sleep(delay)

    return False