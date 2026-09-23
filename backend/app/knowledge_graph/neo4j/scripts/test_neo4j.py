from app.knowledge_graph.neo4j.client import check_neo4j_connection
from app.knowledge_graph.neo4j.schema import initialize_schema


if __name__ == "__main__":
    if not check_neo4j_connection():
        raise RuntimeError("Neo4j connection failed")

    initialize_schema()

    print("Neo4j connection successful")
    print("Neo4j schema initialized")