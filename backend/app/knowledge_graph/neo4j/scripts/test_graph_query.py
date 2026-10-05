from app.knowledge_graph.neo4j.query_repository import Neo4jQueryRepository
from app.knowledge_graph.neo4j.resolution.entity_resolver import EntityResolver, EntityResolution

query_repository = Neo4jQueryRepository()

resolver = EntityResolver(
    query_repository=query_repository,
)


result = resolver.resolve(
    user_id=1,
    repository_id=1,
    entity_name="something",
)

print(result.entity)
print(result.candidates)
print(result.resolved)
print(result.ambiguous)