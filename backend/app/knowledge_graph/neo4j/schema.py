from app.knowledge_graph.neo4j.client import driver


def initialize_schema():
    with driver.session() as session:
        session.run(
            """
            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
            FOR (n:Entity)
            REQUIRE n.id IS UNIQUE
            """
        )