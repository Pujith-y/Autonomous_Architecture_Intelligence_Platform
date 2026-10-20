import pytest

from app.knowledge_graph.semantic.embedding_provider import EmbeddingProvider


class FakeEmbeddingModel:
    def embed(self, texts):
        for _ in texts:
            yield [0.1] * 768

    def query_embed(self, text):
        yield [0.2] * 768


def test_embeds_multiple_documents():
    provider = EmbeddingProvider(model=FakeEmbeddingModel())

    vectors = provider.embed_documents(["function login", "database connection"])

    assert len(vectors) == 2
    assert all(len(vector) == 768 for vector in vectors)


def test_embeds_query():
    provider = EmbeddingProvider(model=FakeEmbeddingModel())

    vector = provider.embed_query("Where is authentication handled?")

    assert len(vector) == 768


def test_empty_documents_return_empty_list():
    provider = EmbeddingProvider(model=FakeEmbeddingModel())

    assert provider.embed_documents([]) == []


def test_empty_query_is_rejected():
    provider = EmbeddingProvider(model=FakeEmbeddingModel())

    with pytest.raises(ValueError):
        provider.embed_query("   ")


def test_wrong_vector_dimension_is_rejected():
    class WrongDimensionModel:
        def embed(self, texts):
            for _ in texts:
                yield [0.1] * 512

        def query_embed(self, text):
            yield [0.1] * 512

    provider = EmbeddingProvider(model=WrongDimensionModel())

    with pytest.raises(ValueError, match="dimension"):
        provider.embed_documents(["test"])
