from app.knowledge_graph.neo4j.query_repository import Neo4jQueryRepository

query_repository = Neo4jQueryRepository()


result = query_repository.find_entity(
    user_id=1,
    repository_id=1,
    entity_name="user",
)

print(result)