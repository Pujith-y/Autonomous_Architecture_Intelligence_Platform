from pathlib import Path
from unittest.mock import Mock

from app.knowledge_graph.semantic.document_builder import SemanticDocument
from app.knowledge_graph.semantic.indexing_service import (
    SemanticIndexingService,
)
from app.repository_model.model import RepositoryModel


def test_index_repository_builds_embeds_and_stores_documents():
    indexer = Mock()
    embedding_provider = Mock()
    vector_store = Mock()

    documents = [
        SemanticDocument(
            entity_id="python.auth.login",
            text="Function: login",
            metadata={
                "entity_id": "python.auth.login",
                "kind": "function",
                "name": "login",
            },
        ),
        SemanticDocument(
            entity_id="python.auth.logout",
            text="Function: logout",
            metadata={
                "entity_id": "python.auth.logout",
                "kind": "function",
                "name": "logout",
            },
        ),
    ]

    vectors = [[0.1] * 768, [0.2] * 768]

    indexer.build_documents.return_value = documents
    embedding_provider.iter_document_embeddings.return_value = [
        (0, vectors),
    ]

    service = SemanticIndexingService(
        indexer=indexer,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    count = service.index_repository(
        repository_model=RepositoryModel(name="test-repo"),
        user_id=1,
        repository_id=2,
    )

    assert count == 2

    indexer.build_documents.assert_called_once()
    embedding_provider.iter_document_embeddings.assert_called_once_with(
        ["Function: login", "Function: logout"],
        batch_size=32
    )
    vector_store.ensure_collection.assert_called_once()
    vector_store.upsert_document_batch.assert_called_once_with(
        documents=documents,
        vectors=vectors,
        user_id=1,
        repository_id=2,
    )


def test_index_repository_skips_storage_when_no_documents_exist():
    indexer = Mock()
    embedding_provider = Mock()
    vector_store = Mock()

    indexer.build_documents.return_value = []

    service = SemanticIndexingService(
        indexer=indexer,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    count = service.index_repository(
        repository_model=RepositoryModel(name="empty-repo"),
        user_id=1,
        repository_id=2,
    )

    assert count == 0
    embedding_provider.embed_documents.assert_not_called()
    vector_store.ensure_collection.assert_not_called()
    vector_store.upsert_documents.assert_not_called()
