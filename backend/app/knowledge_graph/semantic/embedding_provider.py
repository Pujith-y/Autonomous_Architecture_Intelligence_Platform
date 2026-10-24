from collections.abc import Iterable, Iterator

from fastembed import TextEmbedding

from app.config.settings import settings

class EmbeddingProvider:
    """Generate embeddings for code documents and search queries."""

    MODEL_NAME = settings.MODEL_NAME
    VECTOR_SIZE = settings.VECTOR_SIZE

    def __init__(self, model: TextEmbedding | None = None):
        self.model = model or TextEmbedding(model_name=self.MODEL_NAME)

    @staticmethod
    def _to_vector(values: Iterable[float]) -> list[float]:
        vector = [float(value) for value in values]

        if not vector:
            raise ValueError("Embedding model returned an empty vector")

        return vector

    
    def iter_document_embeddings(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> Iterator[tuple[int, list[list[float]]]]:
        """Yield batches of document embeddings with their starting index."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]

            vectors = [
                self._to_vector(embedding)
                for embedding in self.model.embed(batch)
            ]

            if len(vectors) != len(batch):
                raise ValueError(
                    "Embedding count does not match batch size"
                )

            if any(
                len(vector) != self.VECTOR_SIZE
                for vector in vectors
            ):
                raise ValueError(
                    "Unexpected document embedding dimension"
                )

            yield start, vectors

    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_size = 32
        vectors: list[list[float]] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]

            batch_vectors = [
                self._to_vector(embedding)
                for embedding in self.model.embed(batch)
            ]

            if len(batch_vectors) != len(batch):
                raise ValueError(
                    "Embedding count does not match batch size"
                )

            if any(
                len(vector) != self.VECTOR_SIZE
                for vector in batch_vectors
            ):
                raise ValueError(
                    "Unexpected document embedding dimension"
                )

            vectors.extend(batch_vectors)

        if len(vectors) != len(texts):
            raise ValueError(
                "Embedding count does not match document count"
            )

        return vectors

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query text cannot be empty")

        embedding = next(self.model.query_embed(text))
        vector = self._to_vector(embedding)

        if len(vector) != self.VECTOR_SIZE:
            raise ValueError("Unexpected query embedding dimension")

        return vector
