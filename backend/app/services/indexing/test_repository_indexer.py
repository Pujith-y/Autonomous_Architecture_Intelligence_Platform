from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.indexing.repository_indexer import RepositoryIndexer


def test_pipeline_indexes_graph_and_semantics():
    repository = SimpleNamespace(
        id=42,
        user_id=7,
        path=Path("/tmp/sample-repo"),
    )

    discovered_repository = SimpleNamespace(
        name="sample-repo",
        path=Path("/tmp/sample-repo"),
    )

    discovered_repo = SimpleNamespace(
        path=Path("/tmp/sample-repo"),
    )

    model = object()

    indexer = RepositoryIndexer()
    indexer.ingestor = MagicMock()
    indexer.ingestor.ingest.return_value = discovered_repository

    indexer.builder = MagicMock()
    indexer.builder.build.return_value = discovered_repo

    indexer.neo4j_repository = MagicMock()

    semantic_service = MagicMock()
    indexer._build_semantic_indexing_service = MagicMock(
        return_value=semantic_service,
    )

    with (
        patch(
            "app.services.indexing.repository_indexer.RepositoryScanner"
        ) as scanner_class,
        patch(
            "app.services.indexing.repository_indexer.build_repository_graph",
            return_value=model,
        ),
    ):
        scanner_class.return_value.scan.return_value = ([], [])

        indexer._run_pipeline(repository)

    indexer.neo4j_repository.replace_repository_graph.assert_called_once_with(
        model,
        user_id=7,
        repository_id=42,
    )

    indexer._build_semantic_indexing_service.assert_called_once_with(
        str(Path("/tmp/sample-repo")),
    )

    semantic_service.index_repository.assert_called_once_with(
        repository_model=model,
        user_id=7,
        repository_id=42,
    )
