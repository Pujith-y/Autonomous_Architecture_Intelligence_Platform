from app.knowledge_graph.semantic.document_builder import SemanticDocument
from unittest.mock import Mock

from qdrant_client import models

from app.knowledge_graph.semantic.vector_store import QdrantVectorStore


def test_ensure_collection_creates_missing_collection():
    client = Mock()
    client.collection_exists.return_value = False

    store = QdrantVectorStore(client)

    store.ensure_collection()

    client.create_collection.assert_called_once()
    kwargs = client.create_collection.call_args.kwargs

    assert kwargs["collection_name"] == "aaip_code_embeddings"
    assert kwargs["vectors_config"].size == 768
    assert kwargs["vectors_config"].distance == models.Distance.COSINE


def test_ensure_collection_does_not_recreate_existing_collection():
    client = Mock()
    client.collection_exists.return_value = True

    store = QdrantVectorStore(client)

    store.ensure_collection()

    client.create_collection.assert_not_called()


def test_upsert_documents_stores_vectors_and_scoped_metadata():
    client = Mock()
    store = QdrantVectorStore(client)

    document = SemanticDocument(
        entity_id="python.auth.login",
        text="Function: login",
        metadata={
            "entity_id": "python.auth.login",
            "kind": "function",
            "name": "login",
        },
    )
    vector = [0.1] * 768

    store.upsert_documents(
        documents=[document],
        vectors=[vector],
        user_id=1,
        repository_id=2,
    )

    client.upsert.assert_called_once()
    kwargs = client.upsert.call_args.kwargs
    assert kwargs["collection_name"] == "aaip_code_embeddings"
    assert kwargs["wait"] is True

    point = kwargs["points"][0]
    assert point.payload["entity_id"] == (
        "user:1::repo:2::python.auth.login"
    )
    assert point.payload["user_id"] == 1
    assert point.payload["repository_id"] == 2
    assert point.payload["name"] == "login"
    assert len(point.vector) == 768
    assert point.payload["text"] == "Function: login"


def test_upsert_documents_rejects_mismatched_counts():
    client = Mock()
    store = QdrantVectorStore(client)

    try:
        store.upsert_documents(
            documents=[],
            vectors=[[0.1] * 768],
            user_id=1,
            repository_id=2,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "count" in str(exc)


def test_upsert_documents_rejects_wrong_vector_size():
    client = Mock()
    store = QdrantVectorStore(client)

    document = SemanticDocument(
        entity_id="python.auth.login",
        text="Function: login",
        metadata={"kind": "function"},
    )

    try:
        store.upsert_documents(
            documents=[document],
            vectors=[[0.1] * 10],
            user_id=1,
            repository_id=2,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "dimensional" in str(exc)

    client.upsert.assert_not_called()
