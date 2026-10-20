from app.knowledge_graph.semantic.embedding_provider import EmbeddingProvider
from app.knowledge_graph.semantic.indexer import SemanticIndexer
from app.knowledge_graph.semantic.vector_store import QdrantVectorStore
from app.repository_model.model import RepositoryModel


class SemanticIndexingService:
    """Coordinate document creation, embedding, and vector storage."""

    def __init__(
        self,
        indexer: SemanticIndexer,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
    ):
        self.indexer = indexer
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def index_repository(
        self,
        repository_model: RepositoryModel,
        user_id: int,
        repository_id: int,
    ) -> int:
        """Index source entities and return the number of documents stored."""
        documents = self.indexer.build_documents(repository_model)

        if not documents:
            return 0

        vectors = self.embedding_provider.embed_documents(
            [document.text for document in documents]
        )

        self.vector_store.ensure_collection()
        self.vector_store.upsert_documents(
            documents=documents,
            vectors=vectors,
            user_id=user_id,
            repository_id=repository_id,
        )

        return len(documents)
