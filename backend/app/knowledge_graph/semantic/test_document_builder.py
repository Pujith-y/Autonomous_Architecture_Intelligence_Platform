from pathlib import Path

from app.knowledge_graph.semantic.document_builder import (
    SemanticDocumentBuilder,
)
from app.repository_model.entities import Entity
from app.repository_model.enums import EntityKind
from app.repository_model.locations import SourceLocation


def test_builds_document_with_entity_metadata():
    entity = Entity(
        id="repo::python::auth.login",
        kind=EntityKind.FUNCTION,
        name="login",
        qualified_name="auth.login",
        location=SourceLocation(
            file=Path("auth.py"),
            start_line=10,
            end_line=20,
        ),
        language="python",
    )

    document = SemanticDocumentBuilder().build(
        entity,
        "def login():\n    return True",
    )

    assert document is not None
    assert document.entity_id == entity.id
    assert "Entity kind: function" in document.text
    assert "Qualified name: auth.login" in document.text
    assert "def login():" in document.text
    assert document.metadata["file"] == "auth.py"
    assert document.metadata["start_line"] == 10


def test_returns_none_for_empty_source():
    entity = Entity(
        id="repo::python::empty",
        kind=EntityKind.FUNCTION,
        name="empty",
    )

    assert SemanticDocumentBuilder().build(entity, "") is None


def test_supports_entities_without_optional_metadata():
    entity = Entity(
        id="repo::python::simple",
        kind=EntityKind.FUNCTION,
        name="simple",
    )

    document = SemanticDocumentBuilder().build(
        entity,
        "def simple(): pass",
    )

    assert document is not None
    assert document.metadata["entity_id"] == entity.id
    assert "language" not in document.metadata
    assert "file" not in document.metadata
