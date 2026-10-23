
from app.knowledge_graph.semantic.embedding_provider import EmbeddingProvider
from app.knowledge_graph.semantic.vector_store import QdrantVectorStore
from app.knowledge_graph.neo4j.query_repository import Neo4jQueryRepository


class RetrievalService:
    """Combine semantic search results with scoped Neo4j graph evidence."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        graph_repository: Neo4jQueryRepository,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.graph_repository = graph_repository

    def retrieve(
        self,
        query: str,
        user_id: int,
        repository_id: int,
        limit: int = 5,
        relationships_per_entity: int = 10,
    ) -> dict:
        """Return semantic matches enriched with direct graph relationships."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        if not isinstance(user_id, int) or isinstance(user_id, bool):
            raise ValueError("user_id must be an integer")

        if not isinstance(repository_id, int) or isinstance(repository_id, bool):
            raise ValueError("repository_id must be an integer")

        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        if not 1 <= relationships_per_entity <= 100:
            raise ValueError("relationships_per_entity must be between 1 and 100")

        query_vector = self.embedding_provider.embed_query(query.strip())

        matches = self.vector_store.search(
            query_vector=query_vector,
            user_id=user_id,
            repository_id=repository_id,
            limit=limit,
        )

        evidence = []

        for match in matches:
            entity_id = match.get("entity_id")
            if not entity_id:
                continue

            # Resolve the exact namespaced ID, not an ambiguous short name.
            entity = self.graph_repository.get_entity(
                user_id=user_id,
                repository_id=repository_id,
                entity_id=entity_id,
            )

            # A stale vector may point to an entity absent from the graph.
            if entity is None:
                continue

            relationships = self.graph_repository.find_relationships(
                user_id=user_id,
                repository_id=repository_id,
                entity_id=entity_id,
                direction="both",
                limit=relationships_per_entity,
            )

            evidence.append(
                {
                    "entity": entity,
                    "score": match.get("score"),
                    "text": match.get("text", ""),
                    "metadata": match.get("metadata", {}),
                    "relationships": relationships,
                }
            )

        return {
            "query": query.strip(),
            "user_id": user_id,
            "repository_id": repository_id,
            "matches": evidence,
        }
