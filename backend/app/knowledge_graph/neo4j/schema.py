from app.database.neo4j import driver


def initialize_schema():
    with driver.session() as session:
        session.run(
            """
            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
            FOR (n:Entity)
            REQUIRE n.id IS UNIQUE
            """
        )