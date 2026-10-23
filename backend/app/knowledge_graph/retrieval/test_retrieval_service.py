from unittest.mock import Mock

import pytest

from app.knowledge_graph.retrieval.retrieval_service import RetrievalService


@pytest.fixture
def service():
    embedding = Mock()
    embedding.embed_query.return_value = [0.1] * 768

    vector_store = Mock()
    vector_store.search.return_value = [
        {
            "entity_id": "user:7::repo:42::python.auth.login",
            "score": 0.91,
            "text": "def login(): ...",
            "metadata": {"name": "login"},
        }
    ]

    graph = Mock()
    graph.get_entity.return_value = {
        "id": "user:7::repo:42::python.auth.login",
        "name": "login",
        "qualified_name": "auth.login",
    }
    graph.find_relationships.return_value = [
        {"relationship_type": "calls", "direction": "incoming"}
    ]

    return RetrievalService(embedding, vector_store, graph)


def test_retrieve_combines_semantic_and_graph_evidence(service):
    result = service.retrieve(
        query="Where is authentication handled?",
        user_id=7,
        repository_id=42,
    )

    service.embedding_provider.embed_query.assert_called_once_with(
        "Where is authentication handled?"
    )

    service.vector_store.search.assert_called_once_with(
        query_vector=[0.1] * 768,
        user_id=7,
        repository_id=42,
        limit=5,
    )

    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["entity"]["name"] == "login"
    assert match["score"] == 0.91
    assert match["relationships"][0]["relationship_type"] == "calls"


def test_retrieve_uses_exact_scoped_entity_id(service):
    service.retrieve("authentication", user_id=7, repository_id=42)

    service.graph_repository.get_entity.assert_called_once_with(
        user_id=7,
        repository_id=42,
        entity_id="user:7::repo:42::python.auth.login",
    )


def test_retrieve_skips_matches_missing_from_graph(service):
    service.graph_repository.get_entity.return_value = None

    result = service.retrieve("authentication", user_id=7, repository_id=42)

    assert result["matches"] == []
    service.graph_repository.find_relationships.assert_not_called()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": " ", "user_id": 7, "repository_id": 42},
        {"query": "auth", "user_id": True, "repository_id": 42},
        {"query": "auth", "user_id": 7, "repository_id": False},
        {"query": "auth", "user_id": 7, "repository_id": 42, "limit": 0},
        {
            "query": "auth",
            "user_id": 7,
            "repository_id": 42,
            "relationships_per_entity": 0,
        },
    ],
)
def test_retrieve_rejects_invalid_arguments(service, kwargs):
    with pytest.raises(ValueError):
        service.retrieve(**kwargs)

    service.embedding_provider.embed_query.assert_not_called()
