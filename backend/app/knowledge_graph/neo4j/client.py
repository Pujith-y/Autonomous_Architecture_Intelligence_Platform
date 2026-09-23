import time
from neo4j import GraphDatabase
from app.config.settings import settings
from app.core.logger import logger

driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
)

def check_neo4j_connection(max_retries=10, delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            with driver.session() as session:
                result = session.run("RETURN 1 AS value")
                if result.single()["value"] == 1:
                    return True

        except Exception as e:
            logger.warning(
                f"Neo4j not ready (attempt {attempt}/{max_retries}): {e}"
            )

        time.sleep(delay)

    return False