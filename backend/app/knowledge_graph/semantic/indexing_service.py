import pickle
from tempfile import TemporaryFile

from app.knowledge_graph.semantic.embedding_provider import EmbeddingProvider
from app.knowledge_graph.semantic.indexer import SemanticIndexer
from app.knowledge_graph.semantic.vector_store import QdrantVectorStore
from app.repository_model.model import RepositoryModel
from app.core.logger import logger


class SemanticIndexingService:
    """Coordinate document creation, embedding, and vector storage."""

    EMBEDDING_BATCH_SIZE = 32

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
        """Replace a repository's semantic index and return its document count."""
        documents = self.indexer.build_documents(repository_model)

        logger.info("Semantic indexing: built %d documents", len(documents))
        logger.info(
            "Semantic indexing: total document characters=%d",
            sum(len(document.text) for document in documents),
        )

        if not documents:
            self.vector_store.delete_repository(
                user_id=user_id,
                repository_id=repository_id,
            )
            return 0

        logger.info("Semantic indexing: starting batched embedding generation")

        # Keep embeddings on disk rather than accumulating every vector in RAM.
        with TemporaryFile(mode="w+b") as spool:
            total_vectors = 0

            for start, vectors in self.embedding_provider.iter_document_embeddings(
                [document.text for document in documents],
                batch_size=self.EMBEDDING_BATCH_SIZE,
            ):
                pickle.dump((start, vectors), spool)
                total_vectors += len(vectors)

                logger.info(
                    "Semantic indexing: embedded %d/%d documents",
                    total_vectors,
                    len(documents),
                )

            if total_vectors != len(documents):
                raise ValueError(
                    "Embedding count does not match document count"
                )

            logger.info(
                "Semantic indexing: embedding generation completed; vectors=%d",
                total_vectors,
            )

            # Preserve the old index until all embeddings have been generated.
            self.vector_store.ensure_collection()
            self.vector_store.delete_repository(
                user_id=user_id,
                repository_id=repository_id,
            )

            # Read one batch at a time and write it to Qdrant.
            spool.seek(0)

            while True:
                try:
                    start, vectors = pickle.load(spool)
                except EOFError:
                    break

                batch_documents = documents[start : start + len(vectors)]

                self.vector_store.upsert_document_batch(
                    documents=batch_documents,
                    vectors=vectors,
                    user_id=user_id,
                    repository_id=repository_id,
                )

        logger.info(
            "Semantic indexing: stored %d documents",
            len(documents),
        )
        return len(documents)
