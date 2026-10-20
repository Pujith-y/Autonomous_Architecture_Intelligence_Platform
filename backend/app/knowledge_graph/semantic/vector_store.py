from qdrant_client import QdrantClient, models

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
)

from uuid import NAMESPACE_URL, uuid5

from app.knowledge_graph.semantic.document_builder import SemanticDocument

from app.config.settings import settings

class QdrantVectorStore:
    """Store and search semantic embeddings in Qdrant."""

    VECTOR_SIZE = settings.VECTOR_SIZE
    DISTANCE = models.Distance.COSINE

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "aaip_code_embeddings",
    ):
        self.client = client
        self.collection_name = collection_name

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        if self.client.collection_exists(self.collection_name):
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.VECTOR_SIZE,
                distance=self.DISTANCE,
            ),
        )

    
    @staticmethod
    def _graph_entity_id(
        entity_id: str,
        user_id: int,
        repository_id: int,
    ) -> str:
        """Match the entity ID namespace used by Neo4j."""
        prefix = f"user:{user_id}::repo:{repository_id}::"

        if entity_id.startswith(prefix):
            return entity_id

        return f"{prefix}{entity_id}"

    def upsert_documents(
        self,
        documents: list[SemanticDocument],
        vectors: list[list[float]],
        user_id: int,
        repository_id: int,
    ) -> None:
        """Store document vectors and their searchable metadata."""
        if len(documents) != len(vectors):
            raise ValueError(
                "Document count does not match vector count"
            )

        if not documents:
            return

        points = []

        for document, vector in zip(documents, vectors):
            if len(vector) != self.VECTOR_SIZE:
                raise ValueError(
                    f"Expected {self.VECTOR_SIZE}-dimensional vector"
                )

            graph_entity_id = self._graph_entity_id(
                document.entity_id,
                user_id,
                repository_id,
            )

            # Qdrant accepts UUIDs or unsigned integer point IDs.
            point_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"aaip:{graph_entity_id}",
                )
            )

            payload = {
                **document.metadata,
                "entity_id": graph_entity_id,
                "user_id": user_id,
                "repository_id": repository_id,
                "text": document.text,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    
    def search(
        self,
        query_vector: list[float],
        user_id: int,
        repository_id: int,
        limit: int = 5,
    ) -> list[dict]:
        """Search code vectors within a specific repository."""
        if len(query_vector) != self.VECTOR_SIZE:
            raise ValueError(
                f"Expected {self.VECTOR_SIZE}-dimensional query vector"
            )

        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        if not self.client.collection_exists(self.collection_name):
            return []

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                ),
                FieldCondition(
                    key="repository_id",
                    match=MatchValue(value=repository_id),
                ),
            ]
        )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        results = []

        for point in response.points:
            results.append(
                {
                    "entity_id": point.payload.get("entity_id"),
                    "score": point.score,
                    "text": point.payload.get("text"),
                    "metadata": point.payload,
                }
            )

        return results
