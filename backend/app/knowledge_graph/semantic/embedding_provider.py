from collections.abc import Iterable

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

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors = [
            self._to_vector(embedding)
            for embedding in self.model.embed(texts)
        ]

        if len(vectors) != len(texts):
            raise ValueError("Embedding count does not match document count")

        if any(len(vector) != self.VECTOR_SIZE for vector in vectors):
            raise ValueError("Unexpected document embedding dimension")

        return vectors

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query text cannot be empty")

        embedding = next(self.model.query_embed(text))
        vector = self._to_vector(embedding)

        if len(vector) != self.VECTOR_SIZE:
            raise ValueError("Unexpected query embedding dimension")

        return vector
