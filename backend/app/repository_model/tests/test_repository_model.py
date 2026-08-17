from pathlib import Path

from app.repository_model import (
    Entity,
    EntityKind,
    Relationship,
    RelationshipKind,
    RepositoryModel,
    SourceLocation,
)


def test_entity_creation():

    entity = Entity(
        id="class:user-service",
        kind=EntityKind.CLASS,
        name="UserService",
        qualified_name="app.services.UserService",
        language="Python",
    )

    assert entity.id == "class:user-service"
    assert entity.kind == EntityKind.CLASS
    assert entity.name == "UserService"
    assert entity.qualified_name == (
        "app.services.UserService"
    )
    assert entity.language == "Python"


def test_source_location():

    location = SourceLocation(
        file=Path(
            "app/services/user_service.py"
        ),
        start_line=10,
        end_line=50,
        start_column=1,
        end_column=20,
    )

    assert location.file == Path(
        "app/services/user_service.py"
    )

    assert location.start_line == 10
    assert location.end_line == 50
    assert location.start_column == 1
    assert location.end_column == 20


def test_relationship_creation():

    relationship = Relationship(
        source_id="class:user-service",
        target_id="class:base-service",
        kind=RelationshipKind.INHERITS,
    )

    assert relationship.source_id == (
        "class:user-service"
    )

    assert relationship.target_id == (
        "class:base-service"
    )

    assert relationship.kind == (
        RelationshipKind.INHERITS
    )


def test_repository_model():

    user_service = Entity(
        id="class:user-service",
        kind=EntityKind.CLASS,
        name="UserService",
    )

    base_service = Entity(
        id="class:base-service",
        kind=EntityKind.CLASS,
        name="BaseService",
    )

    inheritance = Relationship(
        source_id=user_service.id,
        target_id=base_service.id,
        kind=RelationshipKind.INHERITS,
    )

    repository = RepositoryModel(
        name="example",
        entities=[
            user_service,
            base_service,
        ],
        relationships=[
            inheritance,
        ],
    )

    assert repository.name == "example"
    assert len(repository.entities) == 2
    assert len(repository.relationships) == 1

    assert (
        repository.relationships[0].kind
        == RelationshipKind.INHERITS
    )


def test_entity_metadata():

    entity = Entity(
        id="endpoint:get-users",
        kind=EntityKind.ENDPOINT,
        name="get_users",
        metadata={
            "http_method": "GET",
            "path": "/users",
        },
    )

    assert entity.metadata["http_method"] == "GET"
    assert entity.metadata["path"] == "/users"