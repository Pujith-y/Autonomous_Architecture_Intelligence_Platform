from pathlib import Path

from app.knowledge_graph.semantic.indexer import SemanticIndexer
from app.repository_model.entities import Entity
from app.repository_model.enums import EntityKind
from app.repository_model.locations import SourceLocation
from app.repository_model.model import RepositoryModel


def test_builds_documents_for_repository_entities(tmp_path):
    source_file = tmp_path / "example.py"
    source_file.write_text(
        "def first():\n    return 1\n\n"
        "def second():\n    return 2\n",
        encoding="utf-8",
    )

    first = Entity(
        id="example.first",
        kind=EntityKind.FUNCTION,
        name="first",
        location=SourceLocation(
            file=Path("example.py"),
            start_line=1,
            end_line=2,
        ),
        language="python",
    )

    second = Entity(
        id="example.second",
        kind=EntityKind.FUNCTION,
        name="second",
        location=SourceLocation(
            file=Path("example.py"),
            start_line=4,
            end_line=5,
        ),
        language="python",
    )

    repository_model = RepositoryModel(
        name="example",
        entities=[first, second],
    )

    indexer = SemanticIndexer.for_repository(tmp_path)
    documents = indexer.build_documents(repository_model)

    assert len(documents) == 2
    assert documents[0].entity_id == "example.first"
    assert "return 1" in documents[0].text
    assert documents[1].entity_id == "example.second"
    assert "return 2" in documents[1].text


def test_skips_entities_without_extractable_source(tmp_path):
    repository_model = RepositoryModel(
        name="example",
        entities=[
            Entity(
                id="example.missing",
                kind=EntityKind.FUNCTION,
                name="missing",
                location=SourceLocation(
                    file=Path("missing.py"),
                    start_line=1,
                    end_line=2,
                ),
                language="python",
            ),
            Entity(
                id="example.no_location",
                kind=EntityKind.CLASS,
                name="NoLocation",
            ),
        ],
    )

    indexer = SemanticIndexer.for_repository(tmp_path)

    assert indexer.build_documents(repository_model) == []
